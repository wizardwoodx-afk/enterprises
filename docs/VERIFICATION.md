# Verification

What was actually run against this checkout, on Linux x64 with Node v22.22.3 /
npm 10.9.8, after the Beyond rebrand. Re-run the commands to reproduce.

## Results

| Check | Command | Result |
|---|---|---|
| Install | `npm ci --ignore-scripts` | ✅ 1,415 packages |
| Renderer typecheck | `npx tsc -p apps/desktop/tsconfig.json --noEmit` | ✅ 0 errors |
| Electron typecheck | `npx tsc -p apps/desktop/tsconfig.electron.json --noEmit` | ✅ 0 errors |
| Renderer production build | `npx vite build` (in `apps/desktop`) | ✅ built in 63 s |
| Electron-side suite | `npx vitest run --project electron` | ⚠️ 3,780 passed · 16 failed · 32 skipped (3,828) |
| Icon generator | `python3 tools/generate-beyond-icons.py` | ✅ 86 files, deterministic |
| Icon presence | `python3 tools/generate-beyond-icons.py --check` | ✅ all present |
| Beholders service (Python) | `python -m pytest tests` in `packages/beholders` | ✅ 47 passed |
| Beholders engine import | `python -c "from beholders import Agent, Task, Crew, Process, Flow"` | ✅ imports; telemetry off |
| Beholders renderer | `npx vitest run src/plugins/beholders src/contrib/beholders-plugin.test.tsx` | ✅ 29 passed |

The renderer — the entire UI across ~4,300 files — type-checks and builds clean
with the Beyond branding in place.

The electron-side suite result is **identical to the pre-rebrand baseline**
(3,780 passed, 16 failed), which is the evidence that the rename is internally
consistent: source, assertions, fixtures and i18n catalogs were rewritten
together, and no test regressed. Three rename-induced test failures found on the
first post-rebrand run were fixed (see "Regressions found and fixed").

## Why 16 electron tests fail

All 16 need something this checkout deliberately does not contain. They fail
identically on the pre-rebrand tree:

| Group | Count | Missing input |
|---|---|---|
| Python agent runtime | 5 | `beyond_cli/*.py` — the runtime is not vendored |
| Local gateway spawn | 2 | a runnable gateway binary |
| Electron binary absent | 3 | `node_modules/electron` (blocked download) |
| Build/package tooling | 6 | `pm/lock.json`, `locales/_keys.desktop.json`, a prepared Python interpreter |

Example:

```
python3: can't open file '/home/user/enterprises/beyond_cli/backup_sqlite.py':
[Errno 2] No such file or directory
```

Supplying the runtime, `pm/lock.json`, `locales/` and the Electron binary makes
them pass; none of these are branding concerns.

## Regressions found and fixed

The first post-rebrand run showed 19 failures instead of 16. Three were caused by
the rename and were fixed:

1. **`scripts/build/` was never rewritten.** The debrand sweep skipped any
   directory named `build` (to avoid generated output), which also skipped the
   *source* directory `scripts/build/`. Those files kept the **old env-var
   prefix**, so `after-pack-toolchain` and `mac-sign` still looked for it and
   failed. Fixed by re-running the rewrite against `git ls-files`, which only
   ever lists source.
2. **`batch-sign-binaries.test.ts`** asserted a hard-coded alphabetical order:
   the old executable name sorted *after* `FFMPEG.DLL`, but `Beyond.exe` sorts
   *before* it. Expected order corrected.
3. **`local-pack-publish.test.mjs`** had a fixture repository
   (`beyond-app/beyond`) that disagreed with its own assertion
   (`beyond-agent`). Made consistent.

## Renderer-only development

If you only touch `src/`:

```bash
npm run dev:renderer --workspace apps/desktop   # http://127.0.0.1:5174
```

The renderer expects the preload bridge (`window.beyondDesktop`) to exist, so a
plain browser tab renders the shell without backend behaviour. Use
`npm run dev --workspace apps/desktop` for the real app window.

## Why the packaged build can't run in a sandbox

`npm run build` → `scripts/build/desktop.mjs` → `scripts/stage-native-deps.mjs`
runs `@electron/rebuild` for `node-pty`. That needs:

1. the Electron binary (downloaded from `electronjs.org`), and
2. a native build of `get-windows`, a **Windows-only** helper that node-gyp
   cannot compile on Linux.

Neither is a property of this repository. On a normal workstation:

```bash
npm ci
npm run dev   --workspace apps/desktop
npm run pack  --workspace apps/desktop
```

## Reproduce the full check

```bash
npm ci --ignore-scripts
NODE_OPTIONS=--max-old-space-size=8192 npm run typecheck --workspace apps/desktop
npx tsc -p apps/desktop/tsconfig.electron.json --noEmit
npx vite build                      # in apps/desktop
npx vitest run --project ui         # long: thousands of tests
npx vitest run --project electron   # ~7.5 min
python3 tools/generate-beyond-icons.py --check
```

`NODE_OPTIONS=--max-old-space-size=8192` matters: the renderer's type graph
exhausts Node's default heap and aborts with
`Ineffective mark-compacts near heap limit`.

The Beholders engine is a separate distribution with a Python dependency tree, so
its tests need their own environment:

```bash
cd packages/beholders
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests
```

Without those dependencies the engine-wiring tests skip rather than fail — the
service tests need only pytest.

## Branding guard

`.github/workflows/verify.yml` fails the build if an upstream mark — from either
upstream tree, the desktop app or the crew engine — appears anywhere outside
[`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md), the two `LICENSE` files,
the fixed npm package names and the vendored model-price catalog. See
[BRANDING.md](BRANDING.md) for the full rule.
