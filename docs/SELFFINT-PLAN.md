# SelfFint — research, plan, execution record

**SelfFint** is the finance/ERP surface inside Beyond: a first-class page that
reads a company's books out of **ERPNext** and turns them into the four things a
finance team actually looks at — receivables, GST, input-credit reconciliation
and payroll cost — plus a draft-invoice door back into ERPNext.

This document records what was researched, what was decided, and why. It exists
because "add ERPNext" has two honest answers and only one of them is legal.

---

## 1. Research

### 1.1 What ERPNext is (verified 25 Oct 2026)

| Fact | Value | Source |
|---|---|---|
| Licence | **GPL-3.0-only** | `frappe/erpnext` repository licence file; Wikipedia |
| Current stable | **v16** (v16.32.3, Aug 2026) on Frappe Framework 16 | Wikipedia, release notes |
| v16 requirements | Python **3.14**, Node 24, MariaDB 11.8, Redis/Valkey 6+ | docs.frappe.io installation page, `package.json` on version-16 |
| v15 requirements | Python 3.10+, Node 18+, MariaDB 10.6.6+, Redis 6 | docs.frappe.io |
| Install method | `bench init` + `bench get-app` + a database; or `frappe_docker` (11 containers) | docs.frappe.io |
| Distribution | **Not** a pip package. There is no `pip install erpnext` that gives you a working app | PyPI has no `erpnext` |
| Footprint | 20 GB+ of storage, 4–8 GB RAM recommended | deployment guides |
| GitHub | 40,579★, GPL-3.0, pushed the same day as this check | GitHub API |

### 1.2 What its API gives us (verified)

- Base: `https://<site>/api`
- Documents: `GET|POST|PUT|DELETE /api/resource/<DocType>[/<name>]`
- Whitelisted methods: `POST /api/method/<dotted.path>` (e.g.
  `frappe.auth.get_logged_user`)
- Auth for server-to-server: `Authorization: token <api_key>:<api_secret>`
  (Frappe ≥ 11.0.3; keys generated on the User's *API Access* section)
- Listing: `fields` (JSON array), `filters` (JSON array of
  `[field, operator, value]`), `order_by`, `limit_start`, `limit_page_length`
- **Pagination default is 20.** Read one page and stop and you have silently
  read 5 % of the ledger. This is the single most common integration bug.
- Child tables (`Sales Invoice` → `taxes`, `items`) come back only from the
  single-document endpoint, not from the list endpoint.
- Frappe v15+ also exposes `/api/v2/document/<doctype>`; v1 `/api/resource/` is
  still supported and is what every guide and GSP still uses.
- Errors: 401 (auth), 403 (permission), 404 (missing), **417 (validation)**,
  429 (rate limit), 5xx.

### 1.3 The two possible integrations

**Option A — vendor ERPNext into this repository.** Copy the GPL-3.0-only
source into `packages/erpnext`, mount it as an ASGI app, ship one binary.

- ✗ **Licence**: Beyond is MIT. Linking or combining GPL-3.0-only code into it
  re-licenses the whole product. Unlike the MIT-licensed engine behind Beholders
  (which is why that one could be vendored), ERPNext cannot be copied in.
- ✗ **Impossible to run**: Frappe is not a library. It needs MariaDB, Redis,
  a site database, its own bench layout and a build step. There is no "mount
  Frappe as an ASGI app" — `bench serve` is the app.
- ✗ 20 GB+ payload, and every upgrade would be a fork we own forever.

**Option B — integrate over the API at a process boundary.** Keep ERPNext
where it belongs (its own server, its own GPL obligations, its own database),
and make Beyond a *client* of it: an MIT-licensed connector service plus a
native page.

- ✓ No licence contamination: GPL code never enters the MIT tree; we talk HTTP.
- ✓ Works against a self-hosted site, Frappe Cloud, or docker-compose.
- ✓ The user's books stay the single source of truth — no divergent copy.
- ✓ Testable here, today, with a fake transport.
- ✗ Needs a running ERPNext to be useful against real books (mitigated by a
  demo site with fixture data, so the page is explorable without one).

**Decision: Option B.** Same reasoning that made Beholders a merge (MIT engine)
makes SelfFint a connector (GPL engine). Pretending otherwise would be the one
thing the user asked us not to do: not *properly*.

### 1.4 Why a local mirror at all

Dashboards built by calling ERPNext per render are slow, rate-limited and fail
when the site is down. SelfFint therefore keeps a **SQLite mirror** of the
documents it needs (`Sales Invoice`, `Purchase Invoice`, `Payment Entry`,
`Customer`, `Supplier`, `Employee`, `Salary Slip`), synced incrementally on the
`modified` watermark. Reports run against the mirror in milliseconds, work
offline, and never hammer a production ERP with a dashboard refresh.

The mirror is **read-mostly**: the only write path is creating a *draft* Sales
Invoice, which goes straight to the site (write-through), never into the mirror
first.

---

## 2. Plan

### 2.1 Architecture

```
Beyond desktop (Electron/React)
  └── plugin `self-fint`  ── ctx.rest ──►  /api/plugins/self-fint/*   (gateway)
                                              │
                                              ▼
                             packages/selffint (MIT, stdlib only)
                               api.py      dispatch(method, path, body)
                               sync.py     incremental mirror, paged
                               store.py    SQLite mirror + watermarks
                               reports.py  AR aging, GST, payroll, 2B recon
                               client.py   Frappe REST client (token auth)
                               demo.py     fixture site, no ERPNext needed
                                              │
                                              ▼  HTTPS + token
                                        ERPNext / Frappe site
```

Same shape as Beholders on purpose: `dispatch()` returns `(status, payload)`,
`asgi.py` is a bare ASGI callable the gateway mounts, and the plugin talks only
through `ctx.rest`. One transport, one cache, no core edits.

### 2.2 What ships

| Piece | Contents |
|---|---|
| `packages/selffint/src/selffint/client.py` | `Site`, `FrappeClient`, error taxonomy, `fetch_all` paging, URL/JSON encoding |
| `store.py` | SQLite: `sites`, `docs`, `syncs`; upserts, watermarks, filtered reads |
| `sync.py` | Per-doctype incremental sync, page size 200, partial-failure isolation |
| `reports.py` | AR aging buckets, GST output-tax summary, payroll cost, ITC-at-risk |
| `recon.py` | GSTR-2B vs purchase register matching (normalise → exact → fuzzy → leftovers) |
| `api.py` | `/status`, `/connect`, `/sync`, `/invoices`, `/parties`, `/reports/*`, `/reconcile/2b`, `POST /invoices` (draft, write-through) |
| `demo.py` | A fixture company (Indian GST docs) so the page works with no site |
| `asgi.py` | Mount adapter, 4 MB body cap, JSON errors |
| `tests/` | Client, store/sync, reports, recon, api, asgi — pytest, fake transport |
| `apps/desktop/src/plugins/self-fint/` | Page (Overview / Invoices / Parties / Reports), connect dialog, i18n, api layer, tests, plugin registration (route, sidebar, palette, keybind, statusbar) |

### 2.3 Non-goals (stated, so they are not mistaken for gaps)

- **Not** a second accounting system: no double-entry engine, no GL writes.
- **Not** a Frappe replacement: no doctype builder, no workflows, no printing.
- **Not** a GSP: no GSTR portal calls, no IRN. Those stay in ERPNext (India
  Compliance) where the credentials and the audit trail live.
- **Not** a payroll engine: it reports payroll cost from `Salary Slip`; it does
  not compute statutory deductions. That is `packages/beholders`' sibling
  problem — see `docs/BEHOLDERS.md` for the "compute vs connect" split.

### 2.4 Verification gates

1. `python -m pytest packages/selffint/tests` — client, sync, reports, recon, api.
2. `npx eslint apps/desktop/src/plugins/self-fint` — clean.
3. `tsc -p apps/desktop/tsconfig.json --noEmit` — 0 errors.
4. `npx vitest run src/plugins/self-fint src/contrib/self-fint-plugin.test.tsx`.
5. `npx vite build` — production build clean.
6. `python3 tools/verify-debrand.py`-equivalent (the `debrand` CI job) — no
   upstream names outside `THIRD_PARTY_LICENSES.md`. ERPNext and Frappe are
   upstream names, so they are permitted **only** in that file and in this
   package's own docs where attribution is required — checked explicitly.

---

## 3. Execution record

Filled in as the work landed; see `docs/SELFFINT.md` for the operator-facing
guide (connecting a site, generating API keys, what each report means).

### 3.1 What was built

| Path | What it is |
|---|---|
| `packages/selffint/src/selffint/client.py` | Frappe REST client on `urllib`: token auth, explicit paging, single-document hydration for child tables, status → exception taxonomy |
| `…/store.py` | SQLite mirror (documents, sync state, settings) with `0600` permissions |
| `…/sync.py` | Incremental sync on `modified`, per-doctype isolation, bounded tax-table hydration |
| `…/reports.py` | Ageing by days past due, GST by rate with `exempt`/`unallocated` split, payroll cost |
| `…/recon.py` | GSTR-2B vs purchase register: matched, tax mismatch, missing either side, duplicate, probable |
| `…/demo.py` | A fixture company (2 customers, 2 suppliers, sales and purchase invoices, salary slips, a 2B file) |
| `…/api.py` | `dispatch(method, path, body) -> (status, payload)`; 15 paths |
| `…/asgi.py` | Dependency-free ASGI callable, 4 MB body cap, JSON errors |
| `…/server.py` | `selffint serve` — stdlib HTTP adapter, loopback by default |
| `…/cli.py` | `status / demo / connect / sync / report / invoice / serve` |
| `…/tests/` | 7 modules + fixtures, **118 tests**, including a fake Frappe transport that reproduces the two real-world traps |
| `apps/desktop/src/plugins/self-fint/` | The pane: `plugin.tsx`, `page.tsx`, `api.ts`, `i18n.ts`, plus `api.test.ts` (17 cases) |
| `apps/desktop/src/contrib/self-fint-plugin.test.tsx` | Registration lifecycle (off by default, contributions withdrawn on disable) |

### 3.2 Decisions taken while building (and why)

1. **The tax table is hydrated from the document endpoint.** A list read never
   returns `Sales Invoice.taxes`. A GST report built from list rows would show
   every invoice as exempt. `sync.py` hydrates up to `hydrate_limit` documents
   per sync (200 by default) and reports the remainder as `unallocated` — bounded work, honest
   output.
2. **Ageing buckets are computed from `due_date`.** Every test expectation was
   derived from the demo's own dates rather than guessed; the first
   implementation raised `StopIteration` on a not-yet-due invoice because the
   "current" bucket was written `(0, 0)` closed at both ends. It is now
   `(-inf, 0]`.
3. **An empty filter list is omitted, not sent.** `filters=[]` is not the same
   request as no `filters` on some Frappe versions; the full sync path needed
   the parameter gone. The test was written first and the *code* was changed to
   match — the request is what the real site sees.
4. **`/sync` answers 200 with per-doctype results even when every doctype
   fails.** A site that goes down mid-sync is information the pane has to
   render; a 502 with no detail is not. Errors are per doctype, with the Frappe
   message preserved.
5. **The demo company is a state, not a fallback.** `mode: "demo"` travels on
   every payload, the page badges it, and the CLI prints it. There is no path
   where fixture numbers can be mistaken for a customer's books.
6. **The write path is one draft invoice, created on the site first.** If the
   site rejects it, nothing is mirrored; a failed write cannot leave a ghost.
7. **`unallocated` is tax, not value.** It accumulates the tax an invoice
   charges when its rate/head could not be read, plus any head that is not
   CGST/SGST/IGST/CESS. It is money the report refuses to invent a rate for.

### 3.3 Gates (§2.4), run 25 Oct 2026

| # | Gate | Result |
|---|---|---|
| 1 | `python -m pytest packages/selffint/tests -q` | **118 passed** in 2.9 s (Python 3.11.2, pytest 8, no other packages) |
| 2 | `npx eslint src/plugins/self-fint src/contrib/self-fint-plugin.test.tsx` | clean |
| 3 | `tsc -p apps/desktop/tsconfig.json --noEmit` (8 GB heap) | 0 errors |
| 4 | `npx vitest run src/plugins/self-fint src/contrib/self-fint-plugin.test.tsx` | **23 passed** (17 data-layer, 6 registration) |
| 5 | `npx vite build` | clean, 13.7 s |
| 6 | `verify.yml` ▸ `debrand` (grep for the two upstream product names) + an explicit ERPNext check | clean. One pre-existing write-up line in this plan named the vendored engine's upstream and was reworded; the CI job covers the desktop upstream and the engine, not ERPNext. "Frappe"/"ERPNext" remain only in `packages/selffint/**`, `docs/SELFFINT*.md`, `THIRD_PARTY_LICENSES.md` §2a, the root README/CHANGELOG and the plugin's own metadata — attribution and the integration, never Beyond branding |

### 3.4 Not done, and why

- **No live-site test.** There is no ERPNext instance in this environment and
  standing one up needs 20 GB and 11 containers. The client is instead tested
  against a `Transport` implementation that replays the exact request/response
  shapes recorded in §1.2, including the two traps. This is a real gap: the
  first connection to a customer's site should be treated as a smoke test.
- **No GSTR-2B import UI.** `POST /reconcile/2b` accepts rows already parsed
  from the portal's JSON; parsing the portal export is deliberately left to
  whoever has the file, because the format is versioned by GSTN and changes.
- **No write-back beyond drafts**, by design (see non-goals).
- **`DUPLICATE` detection is per (GSTIN, invoice number)** — it catches a
  supplier filing twice, not a genuine second invoice with a reused number.
