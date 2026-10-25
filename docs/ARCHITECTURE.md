# Architecture

Hermes Desktop is a **front end, not a separate agent**. It drives the same Hermes
runtime, sessions, memory, skills and config that the CLI, TUI and messaging
gateway use. Nothing is duplicated between surfaces.

This document is a map for working in this checkout. The upstream docs —
[`apps/desktop/AGENTS.md`](../apps/desktop/AGENTS.md),
[`DESIGN.md`](../apps/desktop/DESIGN.md),
[`ENGINEERING.md`](../apps/desktop/ENGINEERING.md) and
[`BUILDING.md`](../apps/desktop/BUILDING.md) — remain authoritative on rules and
conventions.

## The three boundaries

```
┌──────────────────────────────────────────────────────────────┐
│ Electron main  (apps/desktop/electron/)                      │
│  backend resolution + probing · process lifetime · windows   │
│  native fs/git/clipboard/screenshot · updater · MSIX         │
└───────────────┬──────────────────────────────────────────────┘
                │ contextBridge → window.hermesDesktop  (narrow, allowlisted)
┌───────────────▼──────────────────────────────────────────────┐
│ React renderer  (apps/desktop/src/)                          │
│  routes, panes, transcript (@assistant-ui), stores, plugins  │
└───────────────┬──────────────────────────────────────────────┘
                │ HTTP + WebSocket, via apps/shared
┌───────────────▼──────────────────────────────────────────────┐
│ Hermes Agent runtime — `hermes serve`                        │
│  tui_gateway JSON-RPC / WS API · tools · memory · skills     │
└──────────────────────────────────────────────────────────────┘
```

- **Electron** resolves and validates a runnable backend, owns native
  capabilities, and exposes a narrow preload bridge.
- **React** owns routes, panes, interaction state and the transcript.
- **Hermes Agent** runs as a headless `hermes serve` process exposing the
  `tui_gateway` JSON-RPC/WebSocket API. The renderer connects through
  `apps/shared`, which the browser dashboard also uses.

`apps/desktop/electron/` is deliberately decomposed into focused modules rather
than one `main.ts` — resolution, probing, health, ownership, recycling, IPC,
windows and updater behaviour each live in their own file with their own tests
(293 non-test modules, colocated `*.test.ts`).

## Renderer composition

| Path | Role |
|---|---|
| `src/app/` | Surfaces: chat, session, artifacts, capabilities, cron, gateway, messaging, profiles, quick-entry, settings, starmap, plugins |
| `src/contrib/` | Contribution registry — panes, titlebar/statusbar items, keybinds, palette commands, routes and themes. Core surfaces register through the same API plugins use |
| `src/components/` | Shared UI (assistant-ui bindings, chat, onboarding, pane shell, primitives) |
| `src/api/` | Typed clients for the gateway HTTP surface, incl. `canonical-protocol.ts` |
| `src/store/` | nanostores atoms — the single source of reactive state |
| `src/plugins/`, `src/sdk/` | Bundled plugins and the public plugin SDK surface |
| `src/themes/`, `src/i18n/` | Theme system and per-profile i18n |
| `src/lib/` | Framework-free helpers: transport, keybinds, preview, clipboard, tour |

State follows a strict rule from `AGENTS.md`: read atoms directly in callbacks
(`$atom.get()`) rather than mirroring reactive values into refs, because a ref
synced by `useEffect` lags one render and produces stale-read bugs. ESLint
enforces this (see `apps/desktop/eslint.config.mjs`).

## Backend resolution

Bundled artifacts run their included payload and report damage instead of
installing a second checkout. Non-bundled builds resolve in order:

1. explicit source-root override (`HERMES_DESKTOP_HERMES_ROOT`)
2. development checkout
3. completed managed install
4. `HERMES_DESKTOP_HERMES` deployment override (packagers such as Nix)
5. bootstrap offer (first-run installer)

Candidates are **probed** before use — HTTP and WebSocket — and the app never
adopts an arbitrary `hermes` on `PATH` or a system Python. A runtime predating
`serve` falls back to headless `dashboard --no-open` for the backend command
only; the dashboard UI is never launched or embedded.

Remote and Hermes Cloud modes reuse the same remote-capability path; only auth
and discovery differ. In remote mode the **gateway host is the execution
boundary** — tools, terminal commands and file operations run there, not on the
machine showing the UI.

## State on disk

User data lives in `HERMES_HOME` — `~/.hermes`, or `%LOCALAPPDATA%\hermes` on
Windows — the same layout a CLI install uses, which is what makes the desktop
and CLI interchangeable. The app's own settings, encrypted connection config and
window state live alongside it in Electron's user data directory.

## Plugins

Plugins extend the app without touching core: UI contributions, tools, hooks,
themes and integrations. Bundled plugins are fenced by ESLint to speak only
`@hermes/plugin-sdk` (+ `react`), never `@/…` internals, so the SDK surface stays
honest — the same isolation a runtime-fetched published plugin gets.

## Testing layers

| Layer | Command | What it covers |
|---|---|---|
| Unit (ui) | `npm run test:ui` | Renderer logic and components (vitest + jsdom) |
| Platform | `npm run test:desktop:platforms` | Electron-side modules (vitest, node) |
| E2E | `npm run test:e2e` | Playwright against a built app (58 specs) |
| Packaging | `npm run test:desktop` | Installer/update lifecycle per artifact type |

`npm run dev:mock` runs `tests-js/scripts/mock-server.ts`, an OpenAI-compatible
mock inference server, so the full boot → gateway → inference → renderer chain
can be exercised without a real model.
