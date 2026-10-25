# SelfFint

The finance surface inside Beyond. SelfFint reads a company's books out of a
live **ERPNext** site and answers the four questions a finance desk asks every
morning:

| Question | Where it is answered |
|---|---|
| How much is owed to us, and how late is it? | **Overview ▸ Ageing**, `report ar` |
| What output tax did we charge, at which rates? | **Reports ▸ GST**, `report gst` |
| How much input credit is actually safe? | **Reports ▸ Input credit**, `report 2b` |
| What does the payroll cost the company? | **Reports ▸ Payroll**, `report payroll` |

Plus one write, deliberately the smallest useful one: a **draft** Sales Invoice.

```
┌──────────────────────────────────────────────────────────────┐
│ apps/desktop/src/plugins/self-fint/     (bundled plugin)      │
│   /self-fint page · sidebar row · ⌘K: open, sync now          │
└───────────────────────────┬──────────────────────────────────┘
                            │  ctx.rest → /api/plugins/self-fint/*
┌───────────────────────────▼──────────────────────────────────┐
│ packages/selffint  (MIT, standard library only)               │
│   api.dispatch()  ← ASGI · CLI · stdlib HTTP                  │
│   reports · recon · sync · store (SQLite mirror) · client     │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTPS, Frappe REST, token auth
┌───────────────────────────▼──────────────────────────────────┐
│ ERPNext site  (GPL-3.0 — a separate program, not a library)   │
└──────────────────────────────────────────────────────────────┘
```

## Why the books stay in ERPNext

ERPNext is **GPL-3.0-only**. It is also not a Python library: a working site is a
Frappe app on MariaDB and Redis, created by `bench`, weighing 20 GB+. Two obvious
integrations are therefore both wrong:

- **Vendor it** into the desktop app → the whole binary becomes GPL-3.0.
- **Depend on it** as a package → there is no such package, and importing
  Frappe's models would bind this code to their schema and their release cycle.

So SelfFint sits at a **process boundary** and speaks the Frappe REST API over
HTTP. Nothing in `packages/selffint` is derived from ERPNext; an ERPNext site is
a separately licensed program that the customer runs and we talk to. The name is
used descriptively — see `THIRD_PARTY_LICENSES.md`.

Two consequences worth knowing:

1. `pyproject.toml` has **zero runtime dependencies**. The client is `urllib`,
   the mirror is `sqlite3`, the web door is hand-rolled ASGI. A plugin must not
   drag a second web framework into the gateway's import graph.
2. **SelfFint never posts to the ledger.** It reads; its one write creates a
   *draft*, which moves no accounting entry. If SelfFint has a bug, the worst
   outcome is a junk draft someone deletes — not a wrong GST return.

## The page

`/self-fint`, one sidebar row, two palette commands (`SelfFint: open`,
`SelfFint: sync now`). It ships **off by default** — a user with no ERPNext site
pays nothing for it. Enable it in Capabilities ▸ Plugins.

| Pane | What it shows |
|---|---|
| **Overview** | Four KPIs (receivables, overdue, output tax, payroll cost), the ageing schedule, document counts, and any sync warning |
| **Invoices** | Searchable sales invoices with due date, total, outstanding, status; the `New invoice` form writes a draft |
| **Parties** | Customers and suppliers from the mirror |
| **Reports** | Ageing by bucket and by customer · GST by rate · input credit against GSTR-2B · payroll cost per employee |

The demo company is a first-class state, not an error: a first launch seeds
fixture books and the page badges them **Demo data**. Nothing about a demo
number looks like a real one — the banner says so, and `status.mode` is `demo`.

## The service

`SelfFintApi.dispatch(method, path, body) -> (status, payload)`. Three doors,
one handler set:

| Door | For |
|---|---|
| `selffint.asgi.asgi_app(api)` | the gateway, mounted at `/api/plugins/self-fint` |
| `selffint.server.serve(api)` | development, and a single-binary install (`selffint serve`) |
| `selffint.cli:main` | cron, shells, CI (`selffint sync`) |

### Routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/health` | liveness |
| `GET` | `/status` | site, mode, per-doctype counts, sync state, warnings |
| `GET` | `/sites` · `DELETE /sites/{id}` | connected sites |
| `POST` | `/connect` | validate credentials against the site, store them |
| `POST` | `/sync` | incremental pull (`{"full": true}` re-reads everything) |
| `POST` | `/demo/seed` | seed the fixture company |
| `GET` | `/invoices` | mirror rows; `?search=` and `?status=` |
| `POST` | `/invoices` | **create a draft** on the site, then mirror it |
| `GET` | `/parties` | `?kind=customer\|supplier&search=` |
| `GET` | `/documents/{doctype}/{name}` | one document, child tables included |
| `GET` | `/reports/ar-aging` | `?as_of=YYYY-MM-DD` |
| `GET` | `/reports/gst` | `?from=&to=` |
| `GET` | `/reports/payroll` | `?month=YYYY-MM` |
| `POST` | `/reconcile/2b` | `{"period": "2026-09", "use_demo": true}` or `{"rows": [...]}` |

Every response is `{"ok": bool, …}`. A failure is a payload with a status code —
401/403 from the site become 502 with a readable message, never a stack trace,
because the pane has to render it.

## What each report means

### Ageing — by days past due, not by invoice age

Most ageing reports age the *invoice*; the number a collections team works from
is the days the payment is **late**. Buckets: not yet due, 1–30, 31–60, 61–90,
over 90. Cancelled invoices and drafts are excluded; a fully paid invoice drops
out. `overdue` is the total of everything past its due date.

`as_of` is a real parameter, not cosmetics: it is what makes month-end
reproducible in a test.

### GST — by rate, with the unallocated pile named

Sales invoices are grouped by tax rate, splitting CGST/SGST (intra-state) from
IGST (inter-state). Two numbers matter beyond the total:

- **exempt** — taxable value on invoices that carried no tax rows at all. In a
  real book this is export/SEZ/zero-rated supply, and it should be explained.
- **unallocated** — tax the document *does* charge (`total_taxes_and_charges`)
  whose rate or head never reached the mirror, plus any tax head that is not
  CGST/SGST/IGST/CESS. It is counted, never guessed: a GST report that quietly
  invents an 18 % row on top of missing detail is worse than one that tells you
  to re-sync.

That second case is the single most common integration failure. `POST
/api/resource/Sales%20Invoice` returns the document *with* its child tables, but
the **list** endpoint returns parents only. SelfFint therefore hydrates the tax
table from the single-document endpoint, bounded per sync — and still reports
what it could not hydrate.

### Input credit — GSTR-2B against the purchase register

Given the portal's 2B rows and your purchase invoices, `recon.py` classifies
each pair:

| Status | Meaning | What to do |
|---|---|---|
| `MATCHED` | GSTIN, invoice number and tax agree | claim it |
| `TAX_MISMATCH` | same document, different tax | query the supplier before claiming the lower figure |
| `MISSING_IN_2B` | you booked it, the supplier has not filed it | **hold the credit** — this is the money at risk |
| `MISSING_IN_BOOKS` | the portal has it, your books do not | book it or query the supplier |
| `DUPLICATE` | the portal lists the same document twice | claim once |
| `PROBABLE` | near-match on GSTIN + amount, invoice number differs | review by hand |

`itc_at_risk` is the rupee summary: credit you have booked that the portal does
not yet support. Invoice numbers are normalised (`INV/001`, `inv-1`, ` INV 1`
are one document) because suppliers hyphenate them differently every month.

### Payroll — cost, not computation

From `Salary Slip`: gross, deductions, net, and the employer's own contribution,
so `cost_to_company = gross + employer_contribution`. SelfFint does **not**
compute PF, ESI, professional tax or TDS — that is the payroll engine's job and
it lives in ERPNext (or `packages/beholders`' sibling problem). If your site's
salary slips are wrong, this report reproduces the error faithfully and says so
by showing the components.

## Connecting a site

1. On the site: **User ▸ API Access ▸ Generate Keys**. The secret is shown once.
2. Grant the user read access to `Customer`, `Supplier`, `Sales Invoice`,
   `Purchase Invoice`, `Salary Slip`, `Employee`, `Company` — plus create on
   `Sales Invoice` if drafts are wanted.
3. Connect:

   ```console
   $ selffint connect --url https://erp.acme.in --key 8f2c… --secret 41aa…
   $ selffint sync
   $ selffint status
   ```

4. Or in the app: **SelfFint ▸ Connect a site**, paste the same three values.

Credentials are stored in the local mirror (mode `0600`) and never leave it —
`/status` reports `has_credentials`, never the values.

Frappe's `permission_query_conditions` can silently narrow rows for a user or a
company. If the totals look low, log in as that user on the site before blaming
the mirror.

## Operating it

```console
$ selffint sync                    # cron this nightly
$ selffint report ar --as-of 2026-10-20
$ selffint report gst --from 2026-04-01 --to 2026-09-30
$ selffint report payroll --month 2026-09
$ selffint report 2b
$ selffint invoice create --customer "Acme Textiles" --item "Consulting:1:50000"
$ selffint serve --port 8790       # dev door, loopback only
```

A mirror lives at `$BEYOND_HOME/selffint/mirror.db` (or `--home`). Deleting it is
safe: the next sync rebuilds it, and nothing in it is authoritative.

Sync is incremental on Frappe's `modified` watermark, per doctype, and isolated:
one doctype that 403s is recorded as failed and the rest still sync.

## Verification

```console
$ python -m pytest packages/selffint/tests -q                # 118 passed
$ npx eslint apps/desktop/src/plugins/self-fint
$ ../../node_modules/.bin/tsc -p apps/desktop/tsconfig.json --noEmit
$ npx vitest run src/plugins/self-fint src/contrib/self-fint-plugin.test.tsx
$ npx vite build
```

The pytest suite drives the client against a fake Frappe transport that
reproduces both real-world traps — the list endpoint hiding child tables, and
the default page length of 20 — so the paging and hydration code is tested
against the failure it exists to prevent.

See `docs/SELFFINT-PLAN.md` for the research and the execution record,
`docs/VERIFICATION.md` for the full gate list, and `packages/selffint/README.md`
for the package itself.

## Non-goals

- **Not** a second accounting system: no double-entry engine, no GL writes.
- **Not** a Frappe replacement: no doctype builder, no workflows, no printing.
- **Not** a GSP: no GSTR portal calls, no IRN. Those stay in ERPNext (India
  Compliance), where the credentials and the audit trail belong.
- **Not** a payroll engine: cost reporting only.
