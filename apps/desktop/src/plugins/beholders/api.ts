/**
 * Beholders data layer. Everything goes through `ctx.rest` — the plugin's own
 * `/api/plugins/beholders/*` REST door (`packages/beholders/src/beholders/service/api.py`,
 * mounted by the gateway). No new transport, no core edits.
 *
 * Fetching, caching, dedupe and invalidation are React Query's job, as with every
 * other plugin. This module owns the query keys, the REST calls and the small
 * amount of client state the page needs.
 *
 * CREWS ARE LOCAL, SO THERE IS NO CONNECTION SCOPING. A crew definition lives in
 * `$BEHOLDERS_HOME/crews` on the machine running the gateway, and every gateway
 * this desktop dials is that same machine — so switching profile must NOT be a
 * cache miss here (unlike kanban, whose boards live on whichever gateway you are
 * pointed at). The keys therefore carry the literal `local` scope, and a run
 * that is in flight survives a profile switch.
 */

import {
  atom,
  CREW_POLL_ACTIVE_MS,
  CREW_POLL_IDLE_MS,
  type CrewBlueprint,
  type CrewBlueprintListResult,
  type CrewDefinition,
  type CrewEvent,
  type CrewEventType,
  type CrewInput,
  type CrewListResult,
  type CrewRun,
  type CrewRunSummary,
  type CrewSummary,
  type DeleteResult,
  isTerminalRun,
  type PluginOs,
  type PluginRestOptions,
  type PluginStorage,
  type PluginTranslate,
  queryClient,
  type RunListResult,
  type RunResult,
  type RunSummaryResult
} from '@beyond/plugin-sdk'

type Rest = <T>(path: string, opts?: PluginRestOptions) => Promise<T>
type Socket = (path: string, onMessage: (data: unknown) => void) => () => void

let rest: null | Rest = null
let os: null | PluginOs = null
let t: PluginTranslate = key => key

const PANELS: readonly BeholderPanel[] = ['create', 'detail', 'edit', 'new']

const STORE_KEYS = {
  lastCrewId: 'lastCrewId',
  panel: 'panel'
} as const

/** The crew whose detail pane is open. Persisted so a restart lands where you left. */
export const $selectedCrewId = atom<string>('')

/** The right-hand pane. Mutually exclusive views of one selection, not modals:
 *  the crew's detail, the blueprint picker, a blank editor, or the editor for
 *  the selected crew. Persisted so a restart lands where the user left. */
export type BeholderPanel = 'create' | 'detail' | 'edit' | 'new'

export const $panel = atom<BeholderPanel>('detail')

/** Crew-list filter. Deliberately NOT persisted: a stale search reads as an
 *  empty library on the next launch. */
export const $search = atom<string>('')

/** The run the detail pane is showing. Empty means "the latest run". */
export const $selectedRunId = atom<string>('')

const CREW_KEY_ROOT = ['beholders'] as const
/** Crews are machine-local, so there is exactly one cache scope. */
const LOCAL_SCOPE = 'local'

export const crewsKey = () => [...CREW_KEY_ROOT, LOCAL_SCOPE, 'crews'] as const
export const crewKey = (crewId: string) => [...CREW_KEY_ROOT, LOCAL_SCOPE, 'crew', crewId] as const
export const blueprintsKey = () => [...CREW_KEY_ROOT, LOCAL_SCOPE, 'blueprints'] as const
export const runsKey = (crewId: string) => [...CREW_KEY_ROOT, LOCAL_SCOPE, 'runs', crewId] as const
export const runKey = (runId: string) => [...CREW_KEY_ROOT, LOCAL_SCOPE, 'run', runId] as const

/** Invalidate everything Beholders caches — after a create/delete/run. */
export function invalidateAll(): void {
  void queryClient.invalidateQueries({ queryKey: CREW_KEY_ROOT })
}

/** Bind the plugin's doors. Called once from `register`. */
export function bindApi(apiRest: Rest, storage: PluginStorage, _socket: Socket, opts: { os: PluginOs; t: PluginTranslate }): () => void {
  rest = apiRest
  os = opts.os
  t = opts.t

  $selectedCrewId.set(storage.get(STORE_KEYS.lastCrewId, ''))
  const saved = storage.get<string>(STORE_KEYS.panel, 'detail')

  // An unknown persisted value (an older build, a hand-edited file) falls back
  // to the detail pane rather than rendering neither.
  $panel.set(saved === 'new' ? 'new' : 'detail')

  const unsubs = [
    $selectedCrewId.listen(id => storage.set(STORE_KEYS.lastCrewId, id)),
    $panel.listen(value => storage.set(STORE_KEYS.panel, value))
  ]

  return () => {
    for (const unsub of unsubs) {
      unsub()
    }

    rest = null
    os = null
    t = key => key
  }
}

function needRest(): Rest {
  if (!rest) {
    throw new Error(t('notReady'))
  }

  return rest
}

// ----------------------------------------------------------------- commands
export async function fetchCrews(): Promise<CrewSummary[]> {
  const result = await needRest()<CrewListResult>('/crews')

  return result.crews
}

export async function fetchCrew(crewId: string): Promise<CrewDefinition> {
  const result = await needRest()<{ crew: CrewDefinition; ok: true }>(`/crews/${encodeURIComponent(crewId)}`)

  return result.crew
}

export async function fetchBlueprints(): Promise<CrewBlueprint[]> {
  const result = await needRest()<CrewBlueprintListResult>('/blueprints')

  return result.blueprints
}

export async function createCrew(input: CrewInput): Promise<CrewDefinition> {
  const result = await needRest()<{ crew: CrewDefinition; ok: true }>('/crews', {
    body: input,
    method: 'POST'
  })

  invalidateAll()

  return result.crew
}

export async function updateCrew(crewId: string, input: CrewInput): Promise<CrewDefinition> {
  const result = await needRest()<{ crew: CrewDefinition; ok: true }>(`/crews/${encodeURIComponent(crewId)}`, {
    body: input,
    method: 'PUT'
  })

  invalidateAll()

  return result.crew
}

export async function deleteCrew(crewId: string): Promise<DeleteResult> {
  const result = await needRest()<DeleteResult>(`/crews/${encodeURIComponent(crewId)}`, { method: 'DELETE' })

  if ($selectedCrewId.get() === crewId) {
    $selectedCrewId.set('')
  }

  invalidateAll()

  return result
}

/** Kick off a run. Resolves as soon as the run is queued (202), not when it ends. */
export async function startRun(crewId: string, inputs: Record<string, unknown> = {}): Promise<CrewRunSummary> {
  const result = await needRest()<RunSummaryResult>(`/crews/${encodeURIComponent(crewId)}/runs`, {
    body: { inputs },
    method: 'POST'
  })

  $selectedRunId.set(result.run.id)
  invalidateAll()

  return result.run
}

export async function fetchRuns(crewId: string): Promise<CrewRunSummary[]> {
  const result = await needRest()<RunListResult>(
    `/runs?crew_id=${encodeURIComponent(crewId)}&limit=25`
  )

  return result.runs
}

export async function fetchRun(runId: string): Promise<CrewRun> {
  const result = await needRest()<RunResult>(`/runs/${encodeURIComponent(runId)}`)

  return result.run
}

export async function cancelRun(runId: string): Promise<CrewRunSummary> {
  const result = await needRest()<RunSummaryResult>(`/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })

  invalidateAll()

  return result.run
}

// ------------------------------------------------------------------- state
/**
 * Whether any run in `runs` is still going — drives the fast poll.
 *
 * Tolerant of `undefined` entries on purpose: React Query calls
 * `refetchInterval(query => …)` BEFORE the first fetch resolves, so the natural
 * call sites pass `[query.state.data]` with nothing in it yet. Throwing there
 * takes the whole page down on mount.
 */
export function anyRunning(runs: readonly (CrewRunSummary | undefined)[] | undefined): boolean {
  return Boolean(runs?.some(run => run !== undefined && !isTerminalRun(run.status)))
}

/** Poll cadence for a query: fast while work is in flight, lazy otherwise. */
export function pollInterval(active: boolean): number {
  return active ? CREW_POLL_ACTIVE_MS : CREW_POLL_IDLE_MS
}

/** A run's events, newest last, de-duplicated by `seq`. */
export function mergeEvents(previous: readonly CrewEvent[] | undefined, incoming: readonly CrewEvent[]): CrewEvent[] {
  const bySeq = new Map<number, CrewEvent>()

  for (const event of previous ?? []) {
    bySeq.set(event.seq, event)
  }

  for (const event of incoming) {
    bySeq.set(event.seq, event)
  }

  return [...bySeq.values()].sort((a, b) => a.seq - b.seq)
}

/** Human-facing one-liner for an event row. */
export function describeEvent(event: CrewEvent): string {
  switch (event.type) {
    case 'crew.run.started':
      return t('event.runStarted')

    case 'crew.task.started':
      return t('event.taskStarted', event.task ?? '')

    case 'crew.task.completed':
      return t('event.taskCompleted', event.task ?? '')

    case 'crew.task.failed':
      return t('event.taskFailed', event.task ?? '')

    case 'crew.run.completed':
      return t('event.runCompleted')

    case 'crew.run.failed':
      return t('event.runFailed', event.error ?? '')

    case 'crew.run.cancelled':
      return t('event.runCancelled')

    case 'crew.log':
      return event.detail ?? t('event.log')

    default:
      return event.type
  }
}

/** Tones for the run badge — mapped to `Badge` variants by the page. */
export function statusTone(status: CrewRun['status']): 'destructive' | 'muted' | 'success' | 'warn' {
  switch (status) {
    case 'succeeded':
      return 'success'

    case 'failed':
      return 'destructive'

    case 'running':

    case 'queued':
      return 'warn'

    case 'cancelled':

    default:
      return 'muted'
  }
}

/** Event types that mean "this run is over". */
export const TERMINAL_EVENTS: readonly CrewEventType[] = [
  'crew.run.cancelled',
  'crew.run.completed',
  'crew.run.failed'
]

/** Native toast when a run finishes — the point of running it off-screen. */
export async function notifyFinished(run: CrewRun): Promise<void> {
  if (!os) {
    return
  }

  const title =
    run.status === 'succeeded'
      ? t('notify.succeeded', run.crew_name)
      : run.status === 'cancelled'
        ? t('notify.cancelled', run.crew_name)
        : t('notify.failed', run.crew_name)

  os.notify({
    body: (run.status === 'succeeded' ? run.result : run.error).slice(0, 240),
    title
  })
}

/**
 * Runs this session has SEEN working. Notification is driven off observation,
 * not off the record's status alone: a run that was already finished when you
 * clicked it must not toast, and clicking between finished runs must not
 * re-toast. Cleared for a run the moment its toast is claimed.
 */
const seenRunning = new Set<string>()
const notifiedRuns = new Set<string>()

/**
 * `fetchRun`, plus the native "your crew finished" toast on the transition out
 * of a running state.
 *
 * Lives in the data layer rather than in a component effect on purpose: the
 * poll IS the transition observer, and a `useEffect` comparing renders would
 * miss a run that finished between two mounts (and the repo forbids mirroring
 * reactive values into refs).
 */
export async function fetchRunWithNotify(runId: string): Promise<CrewRun> {
  const run = await fetchRun(runId)

  if (!isTerminalRun(run.status)) {
    seenRunning.add(run.id)

    return run
  }

  if (seenRunning.has(run.id) && !notifiedRuns.has(run.id)) {
    notifiedRuns.add(run.id)
    void notifyFinished(run)
  }

  return run
}

/** Reset module state between tests. */
export function __resetForTests(): void {
  rest = null
  os = null
  t = key => key
  $search.set('')
  seenRunning.clear()
  notifiedRuns.clear()
}
