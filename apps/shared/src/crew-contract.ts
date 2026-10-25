/**
 * The Beholders crew contract — shared by the desktop renderer and the Python
 * service in `packages/beholders`.
 *
 * This mirrors `packages/beholders/src/beholders/service/models.py` field for
 * field, so a crew the UI creates is exactly the crew the engine runs. Keep the
 * two in step; `apps/desktop/src/plugins/beholders/contract.test.ts` asserts the
 * cases this file documents.
 *
 * Vocabulary is the engine's, deliberately: `Crew`, `Agent`, `Task`, `Flow`,
 * `kickoff`. Only the product name moved. See `docs/BEHOLDERS.md`.
 */

/** Execution strategy. Mirrors the engine's `Process` enum. */
export type CrewProcess = 'hierarchical' | 'sequential'

export type RunStatus = 'cancelled' | 'failed' | 'queued' | 'running' | 'succeeded'

/** Lifecycle events a run emits, in the order the pane renders them. */
export type CrewEventType =
  | 'crew.log'
  | 'crew.run.cancelled'
  | 'crew.run.completed'
  | 'crew.run.failed'
  | 'crew.run.started'
  | 'crew.task.completed'
  | 'crew.task.failed'
  | 'crew.task.started'

export interface CrewAgentSpec {
  role: string
  goal?: string
  backstory?: string
  tools?: string[]
  allow_delegation?: boolean
  max_iter?: number
  verbose?: boolean
}

export interface CrewTaskSpec {
  name: string
  description: string
  expected_output?: string
  /** `CrewAgentSpec.role` of the assignee. Empty means "the crew decides". */
  agent?: string
  /** Names of earlier tasks whose output feeds this one. */
  context?: string[]
  output_file?: string
}

/** The full body of a reusable team. */
export interface CrewDefinition {
  id: string
  name: string
  description?: string
  process: CrewProcess
  /**
   * Which declared agent leads. Only meaningful for `hierarchical`; that role
   * steps out of the worker list and delegates (the engine refuses a manager
   * that also appears in `agents`).
   */
  manager_role?: string
  agents: CrewAgentSpec[]
  tasks: CrewTaskSpec[]
  created_at?: string
  updated_at?: string
}

/** List-view shape — enough to render a card without the body. */
export interface CrewSummary {
  id: string
  name: string
  description: string
  process: CrewProcess
  agent_count: number
  task_count: number
  roles: string[]
  updated_at: string
}

/** Anything the body of a create/update accepts. `id` is server-assigned. */
export type CrewInput = Omit<Partial<CrewDefinition>, 'id'> & Pick<CrewDefinition, 'name'>

export interface CrewEvent {
  /** Monotonic per run, 1-based: a poller resumes with `?since=`. */
  seq: number
  /** UTC ISO-8601. */
  at: string
  type: CrewEventType
  task?: string
  agent?: string
  detail?: string
  summary?: string
  result?: string
  error?: string
  reason?: string
}

export interface CrewRun {
  id: string
  crew_id: string
  crew_name: string
  status: RunStatus
  started_at: string
  finished_at: string | null
  result: string
  error: string
  event_count: number
  inputs: Record<string, unknown>
  events?: CrewEvent[]
}

export type CrewRunSummary = Omit<CrewRun, 'events'>

/** A named, ready-made crew the user can instantiate in one click. */
export interface CrewBlueprint {
  id: string
  name: string
  description: string
  process: CrewProcess
  manager_role?: string
  agents: CrewAgentSpec[]
  tasks: CrewTaskSpec[]
}

/** Every response is `{ ok, … }` so a failure is inspectable, never a throw. */
export interface CrewError {
  ok: false
  error: string
}

export interface CrewHealth extends CrewOk {
  service: 'beholders'
  crew_count: number
  active_runs: number
}

export interface CrewOk {
  ok: true
}

export interface CrewListResult extends CrewOk {
  crews: CrewSummary[]
}

export interface CrewGetResult extends CrewOk {
  crew: CrewDefinition
}

export interface CrewBlueprintListResult extends CrewOk {
  blueprints: CrewBlueprint[]
}

export interface RunListResult extends CrewOk {
  runs: CrewRunSummary[]
}

export interface RunResult extends CrewOk {
  run: CrewRun
}

export interface RunSummaryResult extends CrewOk {
  run: CrewRunSummary
}

export interface DeleteResult extends CrewOk {
  deleted: string
}

/**
 * The `crew.*` JSON-RPC methods the service answers on the gateway — the same
 * handlers behind `packages/beholders/src/beholders/service/rpc.py`.
 */
export const CREW_RPC_METHODS = [
  'crew.blueprints',
  'crew.create',
  'crew.delete',
  'crew.get',
  'crew.list',
  'crew.run',
  'crew.runs',
  'crew.runs.cancel',
  'crew.runs.get',
  'crew.status',
  'crew.update'
] as const

export type CrewRpcMethod = (typeof CREW_RPC_METHODS)[number]

/** Terminal statuses — a run in one of these will never change again. */
export const TERMINAL_RUN_STATUSES: readonly RunStatus[] = ['cancelled', 'failed', 'succeeded']

export const isTerminalRun = (status: RunStatus): boolean => TERMINAL_RUN_STATUSES.includes(status)

/** Poll cadence: fast while something is in flight, lazy when nothing is. */
export const CREW_POLL_ACTIVE_MS = 2_000
export const CREW_POLL_IDLE_MS = 15_000
