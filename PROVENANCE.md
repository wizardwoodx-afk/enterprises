# Provenance

This repository contains a source mirror of **Hermes Desktop**, the native
desktop application for **Hermes Agent** by Nous Research.

## Upstream

| | |
|---|---|
| Repository | https://github.com/NousResearch/hermes-agent |
| Path mirrored | `apps/desktop` (+ its build/test dependency closure) |
| Commit | `4ea8d23cc9f527332ccb1d55359b27741b6ea51b` |
| Commit date | 2026-10-24 19:56:21 -0700 |
| Commit subject | `fix(agent): side-question review fixes (unattended turns, profile-bound leases, billing, attribution)` |
| Snapshot taken | 2026-10-25 |
| License | MIT |

Hermes Desktop shipped as a public preview on 2026-06-02 bundled with Hermes
Agent v0.15.2, and became the full "surface" release in v0.16.0. The commit
mirrored here is upstream `main` after the v0.22.5 release (2026-10-22).

The machine-readable form of this table is [`upstream.json`](upstream.json).

## License

The mirrored source is MIT-licensed, © Nous Research. The upstream license text
is reproduced verbatim in [`LICENSE`](LICENSE), as MIT requires for
redistribution.

```
MIT License — Copyright (c) 2026 Nous Research
```

Files added by this mirror (`README.md`, `PROVENANCE.md`, `upstream.json`,
`docs/`, `tools/`) are provided under the same MIT terms.

Nothing in this repository grants rights to the "Hermes" or "Nous Research"
names or marks. They appear only to identify the origin of the code. This mirror
is **not** affiliated with, sponsored by, or endorsed by Nous Research, and it is
not the official distribution channel — official installers live at
<https://hermes-agent.nousresearch.com/desktop>.

## What was copied

Paths are reproduced **path-identically**, so relative imports resolve the same
way they do upstream (`apps/desktop` → `../shared`, `../../tests-js`,
`../../scripts/…`).

| Path | Purpose |
|---|---|
| `apps/desktop/` | The application: `electron/` main + preload, `src/` React renderer, `e2e/`, `packaging/`, build configs |
| `apps/shared/` | `@hermes/shared` — protocol, transport and types shared with the browser dashboard |
| `tests-js/` | Root JS test suites, plus `scripts/mock-server.ts` (the `dev:mock` inference server) |
| `tests/fixtures/` | JSON fixtures imported by desktop tests |
| `tests/install/e2e-assets/` | Installer/updater smoke assets imported by desktop tests |
| `scripts/` | Build and release tooling the desktop build shells out to (`scripts/build/desktop.mjs`, `bundle-electron-main.mjs`, MSIX/notarize helpers, …) |
| `LICENSE` | Upstream MIT license, verbatim |
| `eslint.config.shared.mjs` | Shared ESLint config, imported by `apps/desktop/eslint.config.mjs` |

## What was deliberately not copied

The upstream monorepo's working tree is ~233 MB across ~21,000 files. The
majority is the Python agent runtime and content catalogs, which the desktop
shell does not compile against — it talks to a running `hermes serve` process
over HTTP/WebSocket instead:

`agent/`, `hermes_cli/`, `gateway/`, `tools/`, `hermes_state*.py`, `skills/`,
`optional-skills/`, `plugins/`, `web/`, `ui-tui/`, `website/`, `docs/`,
`locales/`.

This keeps the mirror reviewable and within repository size limits while
remaining fully buildable as an app. To vendor the runtime as well:

```bash
./tools/sync-upstream.sh --with-agent-core
```

## Modifications

No file under `apps/`, `tests/`, `tests-js/` or `scripts/` has been modified.
The complete, machine-readable list of local changes — each with its reason — is
in [`upstream.json`](upstream.json) under `localAdaptations`. In short:

- `package.json` — root workspace manifest rewritten for the trimmed monorepo
  (workspaces `apps/*` + `tests-js`; `web`/`ui-tui`/lefthook removed).
- `package-lock.json` — regenerated against that manifest.
- `.gitignore` — upstream verbatim, plus a short appended block for mirror-local
  artifacts.
- `README.md` — replaced the 14-byte placeholder with mirror documentation.
- Added: `PROVENANCE.md`, `upstream.json`, `docs/`, `tools/sync-upstream.sh`.

## Reproducing this snapshot

```bash
./tools/sync-upstream.sh --check   # verify the tree matches the pinned commit
./tools/sync-upstream.sh           # or refresh it
```
