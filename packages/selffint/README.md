# SelfFint

The finance surface inside Beyond. SelfFint **reads a company's books out of a
live ERPNext site** — receivables, GST, input-credit reconciliation and payroll
cost — and offers exactly one way back in: a **draft** Sales Invoice.

```console
$ selffint demo                         # a fixture company, no ERP needed
$ selffint connect --url https://erp.acme.in --key KEY --secret SECRET
$ selffint sync
$ selffint report ar --as-of 2026-10-20
$ selffint report gst --from 2026-04-01 --to 2026-09-30
$ selffint report payroll --month 2026-09
$ selffint report 2b                     # input credit against the demo 2B
$ selffint invoice create --customer "Acme Textiles" --item "Consulting:1:50000"
$ selffint serve --port 8790             # the same handlers over HTTP
```

Everything above is one handler set: `SelfFintApi.dispatch(method, path, body)`
returns `(status, payload)`, and the CLI, the ASGI app and the desktop's
`ctx.rest` door all call it. There is no second implementation to drift.

## Why it talks to ERPNext instead of containing it

ERPNext is **GPL-3.0-only** and not distributable as a library — it is a Frappe
*app* that needs MariaDB, Redis and `bench`, roughly 20 GB of disk. Vendoring it
into an MIT desktop app would relicense the whole binary, and shipping it as a
dependency would not work. So SelfFint sits at a process boundary and speaks the
Frappe REST API over HTTP: nothing in this package derives from ERPNext, and an
ERPNext site stays a separately-licensed program the user runs.

That is also why `pyproject.toml` has **no runtime dependencies at all** — the
client is `urllib`, the mirror is `sqlite3`, the ASGI app is hand-rolled.

## What it actually does

| Layer | File | Responsibility |
|---|---|---|
| Transport | `client.py` | Token-auth Frappe REST over `urllib`; explicit paging (the server default is 20 rows); child tables fetched from the single-document endpoint; status → exception taxonomy |
| Mirror | `store.py` | SQLite copy of the doctypes the reports need, with per-doctype `modified` watermarks |
| Sync | `sync.py` | Incremental by `modified`; per-doctype isolation (one broken doctype does not abort the rest); bounded child-row hydration |
| Reports | `reports.py` | Receivables ageing by **past-due** date, GST by rate with unallocated tax called out, payroll cost |
| Recon | `recon.py` | GSTR-2B against the purchase register, with the ITC at risk in rupees |
| Doors | `api.py`, `asgi.py`, `cli.py` | One `dispatch()` behind REST, ASGI and a CLI |
| Demo | `demo.py` | A fixture company so the page works with no ERP running |

A read-mostly mirror is deliberate: Sync is one-way. The only write is
`POST /invoices`, which creates a **draft** on the site and never submits it —
drafts move no ledger entry, so a bug in SelfFint cannot corrupt the books.

## Install and run

```console
$ pip install -e packages/selffint       # no dependencies to resolve
$ selffint demo && selffint status
$ python -m pytest packages/selffint/tests -q
```

Mounting in an ASGI gateway is two lines:

```python
from selffint import SelfFintApi, asgi_app

app.mount("/api/plugins/self-fint", asgi_app(SelfFintApi()))
```

In Beyond, the bundled plugin (`apps/desktop/src/plugins/self-fint`) is the
client: `/self-fint` page, sidebar row, palette commands. It ships **off by
default** — enable it in Capabilities ▸ Plugins.

## Connecting a real site

1. On the ERPNext site: **User ▸ API Access ▸ Generate Keys**. The secret is
   shown once.
2. The user needs read permission on `Customer`, `Supplier`, `Sales Invoice`,
   `Purchase Invoice`, `Salary Slip`, `Employee`, `Company`, plus create on
   `Sales Invoice` if drafts are wanted.
3. `selffint connect <url> --api-key … --api-secret …` — the credentials are
   stored in the local mirror's settings table, never sent anywhere else.
4. `selffint sync`, then read the reports.

Frappe's custom `permission_query_conditions` can silently narrow what a user
sees. If totals look low, check the site as that user before blaming SelfFint.

## Non-goals

- Not a second accounting system: no double-entry engine, no GL writes.
- Not a Frappe replacement: no doctype builder, no workflows, no printing.
- Not a GSP: no GSTR portal calls, no IRN — those stay in ERPNext (India
  Compliance), where the credentials and audit trail live.
- Not a payroll engine: it reports payroll cost from `Salary Slip`; it does not
  compute statutory deductions.

## Licence

MIT, like the rest of Beyond. ERPNext is GPL-3.0 and is used only across a
process boundary; the name is used descriptively. See `docs/SELFFINT.md` in the
Beyond repository for the operator guide and `THIRD_PARTY_LICENSES.md` for the
attribution notice.
