# Beyond

A native desktop app for AI agents — chat with streaming tool output,
side-by-side previews, a file browser, voice, and settings. macOS, Windows and
Linux. No terminal required.

Beyond drives an agent runtime over HTTP and WebSocket: the same sessions,
memory, skills and configuration are shared with the command-line and messaging
surfaces, so nothing starts from zero and nothing is duplicated.

| | |
|---|---|
| **Stack** | Electron 44 · React 19 · Vite 8 (rolldown) · Tailwind 4 · TypeScript 6 |
| **License** | MIT — see [LICENSE](LICENSE) |
| **Attribution** | [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) |
| **Branding** | [docs/BRANDING.md](docs/BRANDING.md) |
| **Size** | 4,760 files · ~57 MB of source |

> Beyond is derived from an MIT-licensed upstream project. All upstream names,
> copyright notices and fixed third-party package identities are recorded in
> [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) — the only file in this
> repository that carries them.

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

Then point the app at a runtime:

```bash
# A — connect to an existing local or remote runtime (Settings → Gateways)
# B — let the app provision its own runtime on first launch
```

User data lives in `BEYOND_HOME` (`~/.beyond`, or `%LOCALAPPDATA%\beyond` on
Windows).

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

See [docs/VERIFICATION.md](docs/VERIFICATION.md) for results of a clean run.

---

## Layout

```
apps/desktop/            the app — electron/ (main + preload), src/ (React renderer), e2e/, packaging/
apps/shared/             @beyond/shared — transport, protocol, types shared with the dashboard
tests-js/                root JS test suites + the mock inference server used by `dev:mock`
tests/fixtures/          fixtures referenced by desktop tests
tests/install/e2e-assets/ install/update smoke assets referenced by desktop tests
scripts/                 build + release tooling the desktop build shells out to
tools/                   Beyond-local tooling: icon generation, upstream sync
```

Inside `apps/desktop`, these guides are authoritative before changing anything:

- [`apps/desktop/AGENTS.md`](apps/desktop/AGENTS.md) — architecture, state ownership, transport, performance and testing rules
- [`apps/desktop/DESIGN.md`](apps/desktop/DESIGN.md) — visual system, motion, keyboard behaviour
- [`apps/desktop/BUILDING.md`](apps/desktop/BUILDING.md) — packaging and release contracts
- [`apps/desktop/ENGINEERING.md`](apps/desktop/ENGINEERING.md) — engineering conventions

## How it works

Three boundaries:

- **Electron** resolves and validates a runnable backend, owns native
  filesystem/git/window capabilities, and exposes a narrow preload bridge
  (`window.beyondDesktop`).
- **React** owns the Desktop routes, panes, interaction state, and the
  `@assistant-ui/react` transcript.
- **The agent runtime** runs as a headless `beyond serve` process exposing the
  `tui_gateway` JSON-RPC/WebSocket API. The renderer connects through
  `apps/shared`, which the browser dashboard uses too.

Backend resolution order (non-bundled builds): explicit source-root override →
development checkout → completed managed install → `BEYOND_DESKTOP_RUNTIME`
deployment override → bootstrap offer. Candidates are probed before use.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Branding

The product name, mark, env-var namespace and asset names are Beyond throughout.
How that was done, and what is intentionally left alone, is documented in
[docs/BRANDING.md](docs/BRANDING.md).

```bash
python3 tools/generate-beyond-icons.py          # regenerate the whole icon set
python3 tools/generate-beyond-icons.py --check  # verify every expected icon exists
```

Requires Pillow (`python3 -m venv .venv && .venv/bin/pip install pillow`).

## Known environment constraints

- **`get-windows`** is a Windows-only native helper in the root-install graph.
  On Linux/macOS `npm ci` can fail building it; use `npm ci --ignore-scripts` if
  you only need typecheck/build/test of the renderer.
- **Packaging** needs the Electron binary *and* an `electron-rebuild` of
  `node-pty`.
- **`tsc -p tsconfig.json`** may exhaust Node's default heap on the renderer's
  type graph; run it with `NODE_OPTIONS=--max-old-space-size=8192`.

## License

MIT — see [LICENSE](LICENSE). Third-party components, package identities and
upstream attribution: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
