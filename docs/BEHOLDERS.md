# Beholders

**Beholders** is Beyond's crew runtime: teams of role-playing agents that work
through an ordered list of tasks, running natively inside the desktop app. This
document covers what it is, how it is wired into Beyond, and how to work on it.

Design rationale and the decision log live in
[`BEHOLDERS-PLAN.md`](./BEHOLDERS-PLAN.md); attribution for the vendored engine
lives in [`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md) §2.

---

## 1. Vocabulary

These words are the **API**, not branding. They are unchanged from the upstream
framework because every example, doc and mental model depends on them:

| Term | Meaning |
|---|---|
| **Agent** | One role: `role`, `goal`, `backstory`, plus `tools`, `max_iter`, `allow_delegation` |
| **Task** | One unit of work: `description`, `expected_output`, an assigned `agent`, and `context` (earlier tasks whose output feeds this one) |
| **Crew** | A team: agents + tasks + a `process` |
| **Process** | `sequential` (one task at a time) or `hierarchical` (a lead delegates) |
| **Flow** | Stateful orchestration *around* crews — the engine's event-driven layer |
| **kickoff** | Run a crew |

Only the **product name** moved: every module, identifier, env var and host
carries the Beholders name now, and the upstream name survives only in the
license files listed at the top.

---

## 2. How it is wired into Beyond

```
┌───────────────────────────────────────────────────────────────┐
│ apps/desktop/src/plugins/beholders/     (bundled plugin)      │
│   /beholders page · sidebar row · ⌘K · ⌘⌥R · statusbar pill    │
└───────────────────────────┬───────────────────────────────────┘
                            │  ctx.rest  →  /api/plugins/beholders/*
┌───────────────────────────▼───────────────────────────────────┐
│ packages/beholders/src/beholders/service/   (this repo)       │
│   BeholdersApi · CrewStore · RunRegistry · CrewRpc · serve()  │
└───────────────────────────┬───────────────────────────────────┘
┌───────────────────────────▼───────────────────────────────────┐
│ packages/beholders/src/beholders/          (vendored engine)  │
│   Agent · Task · Crew · Process · Flow · Memory · Tools       │
└───────────────────────────────────────────────────────────────┘
```

Three properties make this a **merge** rather than a bolt-on:

1. **One transport.** The plugin uses `ctx.rest`, the same namespace-scoped REST
   door every plugin uses (`/api/plugins/<id>/*`). There is no side-channel, no
   second socket protocol, no bespoke loader.
2. **One cache.** Crew queries live in the app's React Query client, so the page
   and the statusbar pill share a request, and a run started from the keyboard
   shortcut updates the page the user is looking at.
3. **One lifecycle.** `defaultEnabled: false`, discovered by
   `discoverBundledPlugins()` — enabled, disabled and reloaded exactly like
   kanban or radio, with every contribution withdrawn on unload.

### The desktop surface

| Where | What |
|---|---|
| Route `/beholders` | The page: crew list, agents, tasks, runs, live timeline |
| Sidebar nav | "Beholders" row, order 45, `organization` codicon |
| ⌘K palette | `beholders.open`, `beholders.runCrew` |
| Keyboard | `mod+alt+r` → run the selected crew (rebindable, shown in the palette) |
| Status bar | count of the selected crew's in-flight runs; hidden when idle |

The page ships **off by default**. A user who never runs a crew pays nothing for
it. Enable it in Capabilities ▸ Plugins.

---

## 3. The service layer

`packages/beholders/src/beholders/service/` is original to Beyond. It is the
seam that makes the engine usable by an application.

| Module | Responsibility |
|---|---|
| `models.py` | Wire models: `AgentSpec`, `TaskSpec`, `CrewDefinition`, `RunRecord`, `RunEvent`, `Process`, `RunStatus` |
| `store.py` | Crew persistence: one JSON file per crew under `$BEHOLDERS_HOME/crews`, atomic writes |
| `runs.py` | `RunRegistry` — off-thread execution, cooperative cancellation, event log, history cap; `EngineExecutor` translates a definition into real engine objects |
| `api.py` | `BeholdersApi` — mount-relative REST handlers plus the starter blueprints |
| `rpc.py` | `CrewRpc` — the `crew.*` JSON-RPC methods, on the same handlers |
| `asgi.py` | Bare ASGI mount for the gateway — the integration seam |
| `server.py` | A stdlib `http.server` adapter (`beholders serve`) for development |
| `cli.py` | `beholders crews / create / run / serve` |

### Three doors, one handler set

`BeholdersApi.dispatch(method, path, body)` is deliberately framework-agnostic —
it returns `(status, payload)`. That keeps the surface testable as plain Python
and lets the same logic back REST, JSON-RPC and the stdlib server without three
implementations drifting apart.

### Mounting it in the gateway

The desktop's REST door calls `/api/plugins/beholders/*`. `beholders.service.asgi`
is a dependency-free ASGI callable, so the mount is two lines wherever the
gateway's app factory is:

```python
from beholders.service import BeholdersApi, asgi_app

app.mount("/api/plugins/beholders", asgi_app(BeholdersApi()))
```

Hand-rolled ASGI rather than Starlette/FastAPI on purpose: a plugin must not drag
a second web framework — with its own pins and middleware — into the gateway's
import graph. `packages/beholders/tests/test_asgi_mount.py` drives the mount through a fake
ASGI host and asserts the exact requests `api.ts` sends.

For development, run the same handlers standalone over stdlib HTTP:

```console
$ pip install -e packages/beholders
$ beholders serve --port 8787
$ curl localhost:8787/api/plugins/beholders/health
```

### JSON-RPC methods

`crew.blueprints` · `crew.create` · `crew.delete` · `crew.get` · `crew.list` ·
`crew.run` · `crew.runs` · `crew.runs.cancel` · `crew.runs.get` ·
`crew.status` · `crew.update`

Error codes: `-32601` unknown method, `-32602` bad params, `-32004` not found,
`-32022` invalid definition, `-32603` internal. Same list, verbatim, in
`apps/shared/src/crew-contract.ts`.

---

## 4. The contract

`apps/shared/src/crew-contract.ts` is the single TypeScript description of the
wire format; `beholders/service/models.py` mirrors it field for field. The
renderer gets it through `@beyond/plugin-sdk` (via `src/sdk/crew.ts`), because
plugins may not import `@beyond/shared` directly.

Drift is a test failure, on both sides:

- `packages/beholders/tests/test_contract_parity.py` — parses the TypeScript and
  asserts every Python model field, the RPC method list, the process values, the
  terminal statuses and the blueprints all agree.
- `apps/desktop/src/plugins/beholders/api.test.ts` — asserts the paths, verbs and
  bodies the client actually sends.

---

## 5. Execution model

A run is a **thread**, not a request. `POST /crews/{id}/runs` returns `202`
immediately with a queued record; the UI polls `GET /runs/{id}` and renders the
event log as it grows.

- **Events** carry a 1-based, monotonic `seq` per run, so a poller can resume.
- **Poll cadence** is 2 s while anything is in flight and 15 s when idle
  (`CREW_POLL_ACTIVE_MS` / `CREW_POLL_IDLE_MS`). An idle app does not keep waking
  the service.
- **Cancellation** is cooperative: the executor checks `should_stop` between
  tasks. A task is an LLM round-trip; killing it mid-call would leave the
  provider stream dangling.
- **History** is capped (50 runs) and only finished runs are evicted, so a long
  run is never dropped while it is still going.
- **Notification**: a native toast fires on the transition out of a running
  state — only for a run this session actually watched running. Clicking a run
  that finished an hour ago does not toast.

### Hierarchical crews

The engine refuses a hierarchical crew without a manager, *and* refuses one whose
manager also appears in the agent list. A definition therefore names its lead
with `manager_role`, and that role **steps out of the worker list**:

```json
{
  "name": "Code Review Board",
  "process": "hierarchical",
  "manager_role": "Review Lead",
  "agents": [{ "role": "Review Lead", "allow_delegation": true }, { "role": "Security Reviewer" }],
  "tasks": [{ "name": "review", "description": "…", "agent": "Review Lead" }]
}
```

`EngineExecutor` builds a crew with `agents=[Security Reviewer]` and
`manager_agent=Review Lead`.

---

## 6. Telemetry is off

Not "opt-out" — off in code. `Telemetry._is_telemetry_disabled` returns `True`
unless `BEHOLDERS_ENABLE_TELEMETRY` is explicitly set, so `Telemetry.__init__`
returns before constructing a `TracerProvider` or an OTLP exporter, and
`_should_execute_telemetry()` short-circuits every span helper. The collector
constant is additionally non-routable (`telemetry.invalid`) as defence in depth.

Beyond is a local-first desktop product: nothing leaves the machine on its own.

---

## 7. Working on it

```console
# Python: the service and its tests need only pytest + the engine's deps
cd packages/beholders
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests          # 47 tests

# Renderer
cd apps/desktop
npx vitest run src/plugins/beholders \
  src/contrib/beholders-plugin.test.tsx    # 32 tests
```

What each gate covers:

| Gate | Catches |
|---|---|
| `compileall` + `from beholders import Agent, Task, Crew, Process, Flow` | the vendored rename broke an import |
| `test_service.py` | REST/RPC/store/registry behaviour, cancellation, history cap |
| `test_engine_wiring.py` | definition → real `Agent`/`Task`/`Crew` translation (LLM stubbed) |
| `test_asgi_mount.py` | the gateway mount stops answering what the plugin sends |
| `test_contract_parity.py` | Python and TypeScript drifted |
| `api.test.ts` | the paths, verbs and bodies the client sends |
| `plugin.test.tsx` | the plugin registers/withdraws every contribution |
| `verify.yml` ▸ `debrand` | an upstream name escaped the license file |

### Adding a blueprint

Append to `BLUEPRINTS` in `service/api.py`. A blueprint is a `CrewDefinition`
without an `id`; `test_blueprints_are_creatable` proves it validates, and
`test_contract_parity.py` proves every field it uses is in the TypeScript
contract.

### Updating the vendored engine

Re-vendor from the pinned upstream commit recorded in
`THIRD_PARTY_LICENSES.md` §2 into `packages/beholders/src`, then apply the
rename in this order — **compound and longest first**, or a shorter rule
corrupts every longer name it has already produced:

| New value | Replaces |
|---|---|
| `beholders_core` | the upstream core package |
| `beholders_cli` | the upstream CLI package |
| `beholders` | the upstream engine package |
| `BEHOLDERS` | the upstream env-var prefix |
| `Beholders` | the product name, in **all** of its casings, mixed-case included |

The exact upstream literals live in the license files, not here. Mixed casing is
the trap: a sweep that handles the all-lowercase and the canonical spelling will
still miss the capital-A-I variant, and one that handles `Xxx` needlessly but not
`xxxYyy` leaves header prefixes behind.

Then re-apply the three non-mechanical edits: the lazy `beholders/__init__.py`,
the telemetry kill switch, and the deleted `beholders/cli/` shim. The parity and
service tests are the check that you got all of it.
