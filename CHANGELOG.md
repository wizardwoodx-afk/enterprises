# Changelog

Notable changes to Beyond. The format follows [Keep a Changelog][kac]; the
project uses [semantic versioning][semver].

[kac]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

### Added

- **SelfFint**, a finance surface that reads a company's books out of a live
  **ERPNext** site: receivables ageing by days past due, GST by rate, input
  credit reconciled against GSTR-2B, and payroll cost — plus one write path, a
  **draft** Sales Invoice.
  - `packages/selffint` (MIT, **no runtime dependencies**): a token-auth Frappe
    REST client on `urllib` with explicit paging and child-table hydration, a
    SQLite mirror with per-doctype watermarks, the reports, the 2B reconciler,
    a `dispatch()` behind ASGI / stdlib HTTP / CLI, and a demo company.
  - `apps/desktop/src/plugins/self-fint`: a `/self-fint` page (Overview,
    Invoices, Parties, Reports), a sidebar row and two palette commands. Off by
    default; enable it in Capabilities ▸ Plugins.
  - `docs/SELFFINT.md` (operator guide) and `docs/SELFFINT-PLAN.md` (research,
    decision, execution record).
- 118 Python tests, including a fake Frappe transport that reproduces the two
  traps that break most integrations: the list endpoint never returns child
  tables, and the default page length is 20.

### Changed

- `THIRD_PARTY_LICENSES.md` gains §2a: ERPNext is **interoperated with, not
  bundled**. No Frappe code lives in this tree, which is what keeps Beyond MIT
  while talking to a GPL-3.0 program.

## [1.0.0] — 2026-10-25

The first release under the Beyond name: the desktop app, rebranded and with a
second agent engine built into it.

### Added

- **Beholders**, an agent-crew engine, merged into the desktop app as a native
  agent rather than a sidecar: the engine is vendored at `packages/beholders`
  (upstream `38db11e`, MIT), wrapped by an original service layer
  (`service/api.py`, `asgi.py`, `runs.py`, `store.py`, `rpc.py`), mounted on the
  app's own gateway at `/api/plugins/beholders`, and driven by one plugin
  (`src/plugins/beholders`) that shares the app's transport, cache and
  notification plumbing with everything else.
- Crew editor: agents, tasks, context links, process and manager, with the same
  validation the service applies, reported inline before submit.
- Run form: the `{placeholders}` in a crew's task descriptions become inputs, so
  a crew cannot be run with an invented subject.
- Run timeline: one stage per task boundary, with the duration measured from
  that task's own started event, the terminal error, and follow-the-run
  scrolling.
- Crew search, a loading skeleton, blueprint picker, and a delete confirmation.
- REST + JSON-RPC doors onto the same handler set, with per-crew run history and
  cancellation.
- `docs/BEHOLDERS.md`, `docs/BEHOLDERS-PLAN.md` and `docs/VERIFICATION.md`
  describing the merge, the plan behind it, and how to re-run every gate.

### Changed

- The app is **Beyond**. The upstream product name appears only in
  `THIRD_PARTY_LICENSES.md`; a CI job (`verify.yml` ▸ `debrand`) fails the build
  if it reappears in source, docs or fixtures.
- Icons, window titles, deep links, package metadata, i18n catalogs and test
  fixtures were rewritten together rather than patched, which is why the
  electron suite still reports its pre-rebrand result.

### Notes

- Beholders ships **off by default**; enable it in Capabilities ▸ Plugins.
- Telemetry in the vendored engine is disabled at import and cannot be turned
  on from the app.
- The engine requires Python ≥ 3.10, < 3.14. `packages/beholders` is not
  published to PyPI and is not installed by `npm ci`.
- No desktop installers are attached to this release: packaging needs build
  inputs (a prepared Python interpreter, the Electron binary, signed-channel
  credentials) that this checkout does not carry. The source archives are the
  deliverable.

### Verification

See `docs/VERIFICATION.md` for the commands and their results. In short:
renderer and electron typechecks clean, renderer build clean, Beholders Python
service 47 passed, Beholders renderer 62 passed, electron suite identical to the
pre-rebrand baseline (3,780 passed · 16 failed · 32 skipped, every failure
needing a build input this checkout lacks).
