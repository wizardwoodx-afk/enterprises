# Beholders × Beyond — merge plan

## What is being merged

| | Source | Role |
|---|---|---|
| **Beyond** (this repo) | Electron + React desktop shell | the surface: panes, chat, projects, gateway transport |
| **The upstream crew engine** (a Python multi-agent framework) | multi-agent engine | the crew: role-based agents, tasks, crews, flows |

Nobody is "merged into" a chat window by copying files around. Beyond talks to an
agent runtime over a JSON-RPC/WebSocket gateway (`apps/shared/src/json-rpc-gateway.ts`,
contract in `gateway-contract.openrpc.json`). The engine is a Python library with no
such surface. So a real merge has three layers:

```
┌───────────────────────────────────────────────────────────────┐
│ Beyond desktop (Electron + React)                             │
│   plugins/beholders  →  /beholders pane, sidebar row, palette  │
└───────────────────────────┬───────────────────────────────────┘
                            │  crew.* JSON-RPC over the existing channel
┌───────────────────────────▼───────────────────────────────────┐
│ beholders.service  (new)                                      │
│   CrewService · run registry · event fan-out · REST/WS adapters│
└───────────────────────────┬───────────────────────────────────┘
┌───────────────────────────▼───────────────────────────────────┐
│ beholders  (debranded upstream engine, vendored)               │
│   Agent · Task · Crew · Process · Flow · Memory · Tools        │
└───────────────────────────────────────────────────────────────┘
```

## Decisions

1. **Vendor the engine, don't reimplement it.** The upstream engine's two
   packages (538 files + 40 files) are copied path-for-path and renamed to
   `beholders` / `beholders_core`. Same approach as the desktop mirror: mechanical,
   auditable, and re-runnable.
2. **Keep the domain vocabulary.** `Crew`, `Agent`, `Task`, `Flow`, `Process`,
   `kickoff` are the API, not branding. Renaming them would break every example
   and the mental model. Only the *product* name moves.
3. **The service layer is the actual merge.** A new `beholders.service` package
   adapts the engine to Beyond's transport: it owns a run registry, streams
   agent/task lifecycle events, and exposes `crew.*` methods that match the
   gateway contract shape used everywhere else in the app.
4. **The UI is a bundled plugin**, not a core edit. Beyond's plugin system exists
   for exactly this (see `src/plugins/README.md`): `ctx.register` contributes a
   route, a sidebar row, a palette command and a statusbar item; `ctx.rest` and
   `ctx.socket` carry the traffic. No core files change.
5. **Attribution stays in `THIRD_PARTY_LICENSES.md`**, matching the rule already
   enforced by CI for the desktop.

## Deliverables

| Path | What |
|---|---|
| `packages/beholders/src/beholders/` | debranded engine (vendored) |
| `packages/beholders/src/beholders_core/` | debranded core (vendored) |
| `packages/beholders/src/beholders/service/` | **new** — run registry, JSON-RPC methods, event stream, REST router |
| `packages/beholders/pyproject.toml` | distribution metadata, `beholders` CLI entry point |
| `packages/beholders/tests/` | service-level tests (no LLM calls) |
| `apps/desktop/src/plugins/beholders/` | **new** — the `/beholders` pane |
| `apps/shared/src/crew-contract.ts` | **new** — shared `crew.*` types |
| `docs/BEHOLDERS.md` | architecture + protocol |
| `THIRD_PARTY_LICENSES.md` | §2 records the engine's attribution |

## Verification gates

- `python -m compileall` over the vendored tree (catches rename breaks in imports
  and string-eval paths).
- Import smoke test: `from beholders import Agent, Task, Crew, Process, Flow`.
- Service tests: register a crew, run it against a stub LLM, assert event order.
- TypeScript: `tsc` clean for renderer + electron.
- Branding audit: no upstream engine name outside the license files.
- The existing electron suite must not regress (baseline 3,780 passed).
