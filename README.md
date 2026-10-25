# Hermes Desktop — full source mirror

The complete source of **Hermes Desktop**, the native desktop app for
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by
[Nous Research](https://nousresearch.com), vendored into this repository so it
builds, runs and can be modified here without cloning upstream.

Same agent, same skills, same memory as the CLI and gateway — in a native window
with streaming tool output, side-by-side previews, a file browser, voice, and
settings. macOS, Windows and Linux.

| | |
|---|---|
| **Upstream** | [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) — `apps/desktop` |
| **Pinned commit** | [`4ea8d23`](https://github.com/NousResearch/hermes-agent/commit/4ea8d23cc9f527332ccb1d55359b27741b6ea51b) · 2026-10-24 |
| **License** | MIT — see [LICENSE](LICENSE) and [PROVENANCE.md](PROVENANCE.md) |
| **Stack** | Electron 44 · React 19 · Vite 8 (rolldown) · Tailwind 4 · TypeScript 6 |
| **Vendored size** | 4,760 files · ~57 MB (source only, no build output) |

> This is a **mirror, not a fork.** No upstream source file has been modified.
> The only changes are the mirror-level manifests and docs listed in
> [`upstream.json`](upstream.json) → `localAdaptations`.

---

## Quick start

```bash
npm ci                              # required: deps hoist to this root, the app will not build without them
npm run dev --workspace apps/desktop   # vite renderer + electron main, hot reload
```

Renderer-only loop (fast, no Electron download):

```bash
npm run dev:renderer --workspace apps/desktop   # http://127.0.0.1:5174
```

`npm ci` must run **from this repository root**, not from `apps/desktop`. The
desktop workspace's dependencies are hoisted here, and
`apps/desktop/scripts/assert-root-install.mjs` fails the build with an
explanatory message if it finds a partial install.

Then point the app at a runtime, in one of two ways:

```bash
# A — use an existing Hermes install (shares config, keys, sessions, skills)
hermes desktop

# B — let the app install/provision its own runtime on first launch
#     (first-run screen: "Connect to existing Hermes" or local install)
```

## Build and package

```bash
npm run build --workspace apps/desktop     # vite renderer + bundled electron main
npm run pack  --workspace apps/desktop     # unpacked app for the current OS
npm run dist:mac | dist:win | dist:linux   # installers (run on that OS)
```

Packaging requires the Electron binary and a native rebuild of `node-pty`, so it
needs a normal network path to `electronjs.org` (see
[Known environment constraints](#known-environment-constraints)).

## Verify

```bash
npm run typecheck --workspace apps/desktop   # renderer + electron projects
npm run lint      --workspace apps/desktop
npm run test      --workspace apps/desktop   # vitest: ui + electron + node projects
npm run test:e2e  --workspace apps/desktop   # playwright, needs a built app
```

See [docs/VERIFICATION.md](docs/VERIFICATION.md) for the exact results of a clean
run in this checkout.

---

## Layout

The tree is **path-identical to upstream**, so every relative import
(`../shared`, `../../tests-js`, `../../scripts/…`) resolves exactly as it does in
the monorepo. That is deliberate: it keeps re-syncs mechanical.

```
apps/desktop/            the app — electron/ (main + preload), src/ (React renderer), e2e/, packaging/
apps/shared/             @hermes/shared — transport, protocol, types shared with the dashboard
tests-js/                root JS test suites + the mock inference server used by `dev:mock`
tests/fixtures/          fixtures referenced by desktop tests
tests/install/e2e-assets/ install/update smoke assets referenced by desktop tests
scripts/                 build + release tooling the desktop build shells out to
tools/sync-upstream.sh   re-sync this mirror against upstream
upstream.json            pinned provenance manifest (read by the sync tool)
```

Inside `apps/desktop`, the upstream docs are the authoritative guides and are
worth reading before changing anything:

- [`apps/desktop/AGENTS.md`](apps/desktop/AGENTS.md) — architecture, state ownership, transport, performance and testing rules
- [`apps/desktop/DESIGN.md`](apps/desktop/DESIGN.md) — visual system, motion, keyboard behaviour
- [`apps/desktop/BUILDING.md`](apps/desktop/BUILDING.md) — packaging and release contracts
- [`apps/desktop/ENGINEERING.md`](apps/desktop/ENGINEERING.md) — engineering conventions

## How it works

Three boundaries, from the upstream README:

- **Electron** resolves and validates a runnable backend, owns native
  filesystem/git/window capabilities, and exposes a narrow preload bridge
  (`window.hermesDesktop`).
- **React** owns the Desktop routes, panes, interaction state, and the
  `@assistant-ui/react` transcript.
- **Hermes Agent** runs as a headless `hermes serve` process exposing the
  `tui_gateway` JSON-RPC/WebSocket API. The renderer connects through
  `apps/shared`, which the browser dashboard uses too.

Backend resolution order (non-bundled builds): explicit source-root override →
development checkout → completed managed install → `HERMES_DESKTOP_HERMES`
deployment override → bootstrap offer. Candidates are probed before use; a
runtime that predates `serve` falls back to headless `dashboard --no-open`.
Bundled artifacts run their payload directly and never adopt a `hermes` on
`PATH`. User data lives in `HERMES_HOME` (`~/.hermes`, or
`%LOCALAPPDATA%\hermes` on Windows) — the same layout a CLI install uses, which
is why the two are interchangeable.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What is and isn't here

Included: everything needed to build, run, test and package the desktop shell.

Excluded: the Python agent runtime (`agent/`, `hermes_cli/`, `gateway/`,
`tools/`, `hermes_state*.py`), the skill catalogs, `web/`, `ui-tui/`, `website/`
and `locales/`. That is ~233 MB / 21k files, none of it needed to compile the
app. Use the official installer for the runtime, or vendor it deliberately:

```bash
./tools/sync-upstream.sh --with-agent-core
```

## Keeping in sync

```bash
./tools/sync-upstream.sh --check     # report drift against the pinned commit
./tools/sync-upstream.sh             # apply the pinned commit
./tools/sync-upstream.sh --latest    # follow upstream main
./tools/sync-upstream.sh --ref <sha> # pin to a specific commit or tag
```

`--check` exits non-zero on drift, so it drops straight into CI. The tool never
overwrites the mirror-local files (`package.json`, `package-lock.json`,
`README.md`, `.gitignore`); it stages upstream's copies under `.upstream/reference/`
for diffing. After a sync, update `source.commit` in
[`upstream.json`](upstream.json).

## Known environment constraints

These are characteristics of the upstream app, not defects introduced here.

- **`get-windows`** is a Windows-only native helper that appears in the
  root-install graph. On Linux/macOS `npm ci` can fail building it; use
  `npm ci --ignore-scripts` if you only need typecheck/build/test of the
  renderer. Full `npm run dev`/`dist` needs it resolved on a supported OS.
- **Packaging** needs the Electron binary *and* an `electron-rebuild` of
  `node-pty`. In a sandbox with only registry access, download the Electron
  binary from `electronjs.org` first, or skip packaging.
- **`tsc -p tsconfig.electron.json`** reports one pre-existing `TS2307` for
  `electron/channel-build-version.test.ts` importing a `.mjs` asset with
  `allowJs: false`. It reproduces on upstream source unchanged.

## License and attribution

MIT. The app is © Nous Research; see [LICENSE](LICENSE) and
[PROVENANCE.md](PROVENANCE.md). "Hermes" and "Nous Research" are used only to
describe the origin of this code — this mirror is not affiliated with or
endorsed by Nous Research.
