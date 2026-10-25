# Verification

What was actually run against this mirror, on Linux x64 with Node v22.22.3 /
npm 10.9.8, and what the results mean. Re-run the commands to reproduce.

## Results

| Check | Command | Result |
|---|---|---|
| Install | `npm ci --ignore-scripts` | ✅ 1,415 packages |
| Renderer typecheck | `npx tsc -p apps/desktop/tsconfig.json --noEmit` | ✅ 0 errors |
| Renderer production build | `npx vite build` (in `apps/desktop`) | ✅ built in 54 s |
| Unit tests (sampled) | `npx vitest run --project ui src/api/sessions.test.ts src/app/open-session.test.ts` | ✅ 46/46 tests |
| Electron-side suite | `npx vitest run --project electron` | ⚠️ 3,780 passed · 16 failed · 32 skipped (3,828) |
| Electron typecheck | `npx tsc -p tsconfig.electron.json --noEmit` | ⚠️ 1 pre-existing error (below) |
| Upstream drift | `./tools/sync-upstream.sh --check` | ✅ in sync with `4ea8d23` |
| Packaged build | `npm run build` / `npm run pack` | ❌ blocked in this sandbox (below) |

The renderer — 4,315 files, the entire UI — compiles and type-checks clean at the
pinned commit. That is the meaningful signal that the vendor is complete.

## The 16 failing electron tests

Every failure is a test that **shells out to the Python agent runtime**, which
this mirror intentionally does not vendor (`hermes_cli/*.py`, e.g.
`hermes_cli/backup_sqlite.py`, `gui_uninstall.py`, `cron.py`). Example:

```
python3: can't open file '/home/user/enterprises/hermes_cli/backup_sqlite.py':
[Errno 2] No such file or directory
```

They pass in a full upstream checkout. To satisfy them here:

```bash
./tools/sync-upstream.sh --with-agent-core
```

This is a scoping consequence of a source-only mirror, not a code defect.

## The pre-existing electron typecheck error

```
electron/channel-build-version.test.ts(321,22): error TS2307:
Cannot find module '../../../tests/install/e2e-assets/bundle-smoke-metadata.mjs'
```

The file exists at exactly that path. The cause is the project's own config:
`tsconfig.json` sets `allowJs: false`, so TypeScript cannot resolve a `.mjs`
import without a matching `.mts` declaration, and upstream ships none for this
asset. Forcing `--allowJs` makes the module resolve and replaces the error with
`TS6307`/`TS6059` project-include violations — confirming the file is found and
the config is the constraint. The failure reproduces on unmodified upstream
source and affects a test file only.

## Why the packaged build can't run here

`npm run build` → `scripts/build/desktop.mjs` → `scripts/stage-native-deps.mjs`
runs `@electron/rebuild` for `node-pty`. That needs two things this sandbox
lacks:

1. the Electron binary (downloaded from `electronjs.org`, which is not on the
   allowed egress list — `ELECTRON_SKIP_BINARY_DOWNLOAD=1` was used for install), and
2. a successful native build of `get-windows`, a **Windows-only** helper that
   node-gyp cannot compile on Linux.

Neither is a property of this mirror. On a normal workstation:

```bash
npm ci
npm run dev   --workspace apps/desktop
npm run pack  --workspace apps/desktop
```

## Renderer-only development

If you only touch `src/`, skip Electron entirely:

```bash
npm run dev:renderer --workspace apps/desktop   # http://127.0.0.1:5174
```

The renderer expects the preload bridge (`window.hermesDesktop`) to exist, so a
plain browser tab renders a shell without backend behaviour. Use
`npm run dev --workspace apps/desktop` for the real app window.

## Reproduce the full check

```bash
npm ci
NODE_OPTIONS=--max-old-space-size=8192 npm run typecheck --workspace apps/desktop
npm run test:ui  --workspace apps/desktop     # long: thousands of tests
npm run test:desktop:platforms                # electron-side suite
./tools/sync-upstream.sh --check
```

`NODE_OPTIONS=--max-old-space-size=8192` matters: the renderer's type graph is
large enough to exhaust Node's default heap (the run aborts with
`Ineffective mark-compacts near heap limit`).
