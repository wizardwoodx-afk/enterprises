/**
 * The Beholders page: crews on the left, the selected crew (agents, tasks,
 * runs) on the right, and the live timeline under it.
 *
 * Everything here is SDK-only — `useQuery`, the design-language primitives,
 * `host.navigate`, `ctx.os`. No `@/…` imports, so this file would compile
 * unchanged as a runtime-fetched published plugin.
 */

import {
  Badge,
  Button,
  cn,
  Codicon,
  type CrewBlueprint,
  type CrewDefinition,
  type CrewEvent,
  type CrewRun,
  type CrewRunSummary,
  type CrewSummary,
  EmptyState,
  ErrorState,
  host,
  Tip,
  useMutation,
  useQuery,
  useQueryClient,
  useValue
} from '@beyond/plugin-sdk'
import type { ReactNode } from 'react'

import {
  $panel,
  $selectedCrewId,
  $selectedRunId,
  anyRunning,
  blueprintsKey,
  cancelRun,
  createCrew,
  crewKey,
  crewsKey,
  deleteCrew,
  describeEvent,
  fetchBlueprints,
  fetchCrew,
  fetchCrews,
  fetchRuns,
  fetchRunWithNotify,
  invalidateAll,
  pollInterval,
  runKey,
  runsKey,
  startRun,
  statusTone
} from './api'
import { type BeholderMessages, useBeholderI18n } from './i18n'

// ------------------------------------------------------------------ helpers
function StatusBadge({ k, status }: { k: BeholderMessages; status: CrewRun['status'] }) {
  const label = {
    cancelled: k.statusCancelled,
    failed: k.statusFailed,
    queued: k.statusQueued,
    running: k.statusRunning,
    succeeded: k.statusSucceeded
  }[status]

  return (
    <Badge size="xs" variant={statusTone(status)}>
      {(status === 'running' || status === 'queued') && <Codicon name="loading" size="0.6rem" />}
      {label}
    </Badge>
  )
}

function Section({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[0.6875rem] font-semibold tracking-wide text-(--ui-text-tertiary) uppercase">{title}</h3>
      {children}
    </section>
  )
}

// ------------------------------------------------------------------- crew row
function CrewRow({ crew, selected }: { crew: CrewSummary; selected: boolean }) {
  return (
    <button
      className={cn(
        'flex w-full flex-col gap-1 rounded-[3px] px-2 py-1.5 text-left transition-colors',
        selected ? 'bg-(--chrome-action-hover) text-foreground' : 'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover)'
      )}
      onClick={() => $selectedCrewId.set(crew.id)}
      type="button"
    >
      <span className="flex items-center gap-1.5">
        <span className="truncate text-xs font-medium">{crew.name}</span>
        <Badge size="xs" variant="muted">
          {crew.process}
        </Badge>
      </span>
      <span className="truncate text-[0.6875rem] text-(--ui-text-tertiary)">{crew.description || '—'}</span>
      <span className="flex items-center gap-2 text-[0.625rem] text-(--ui-text-tertiary)">
        <span>{crew.agent_count} agents</span>
        <span aria-hidden>·</span>
        <span>{crew.task_count} tasks</span>
      </span>
    </button>
  )
}

// --------------------------------------------------------------- new crew form
function BlueprintCard({
  blueprint,
  busy,
  onUse
}: {
  blueprint: CrewBlueprint
  busy: boolean
  onUse: (blueprint: CrewBlueprint) => void
}) {
  const k = useBeholderI18n()

  return (
    <div className="flex flex-col gap-1.5 rounded-[3px] border border-(--ui-stroke-secondary) p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium">{blueprint.name}</span>
        <Badge size="xs" variant={blueprint.process === 'hierarchical' ? 'warn' : 'muted'}>
          {blueprint.process}
        </Badge>
      </div>
      <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{blueprint.description}</p>
      <p className="text-[0.625rem] text-(--ui-text-tertiary)">
        {blueprint.agents.map(agent => agent.role).join(' · ')}
      </p>
      <div>
        <Button disabled={busy} onClick={() => onUse(blueprint)} size="xs" variant="secondary">
          <Codicon name="add" size="0.7rem" />
          {k.fromBlueprint}
        </Button>
      </div>
    </div>
  )
}

function NewCrewPanel() {
  const k = useBeholderI18n()
  const queryClient = useQueryClient()

  const { data: blueprints, error: blueprintsError, isLoading } = useQuery({
    queryFn: fetchBlueprints,
    queryKey: blueprintsKey(),
    staleTime: Infinity
  })

  const create = useMutation({
    mutationFn: (blueprint: CrewBlueprint) =>
      createCrew({
        agents: blueprint.agents,
        description: blueprint.description,
        manager_role: blueprint.manager_role,
        name: blueprint.name,
        process: blueprint.process,
        tasks: blueprint.tasks
      }),
    onSuccess: crew => {
      queryClient.setQueryData(crewKey(crew.id), crew)
      $selectedCrewId.set(crew.id)
      $panel.set('crews')
      host.notify({ message: `${crew.name} created` })
    }
  })

  if (isLoading) {
    return <p className="text-xs text-(--ui-text-tertiary)">{k.loading}</p>
  }

  if (blueprintsError) {
    return <ErrorState description={(blueprintsError as Error).message} title={k.notReady} />
  }

  return (
    <div className="flex flex-col gap-2">
      {create.error && <ErrorState description={(create.error as Error).message} title={k.newCrew} />}
      {(blueprints ?? []).map(blueprint => (
        <BlueprintCard blueprint={blueprint} busy={create.isPending} key={blueprint.id} onUse={create.mutate} />
      ))}
    </div>
  )
}

// ------------------------------------------------------------------- crew body
function AgentList({ crew, k }: { crew: CrewDefinition; k: BeholderMessages }) {
  return (
    <Section title={k.agents}>
      <ul className="flex flex-col gap-1.5">
        {crew.agents.map(agent => {
          const isManager = crew.manager_role === agent.role

          return (
            <li className="flex flex-col gap-0.5 rounded-[3px] bg-(--ui-bg-quaternary) p-2" key={agent.role}>
              <span className="flex items-center gap-1.5">
                <Codicon name="person" size="0.7rem" />
                <span className="text-xs font-medium">{agent.role}</span>
                {isManager && (
                  <Badge size="xs" variant="default">
                    {k.manager}
                  </Badge>
                )}
                {agent.allow_delegation && (
                  <Badge size="xs" variant="outline">
                    delegate
                  </Badge>
                )}
              </span>
              {agent.goal && <span className="text-[0.6875rem] text-(--ui-text-secondary)">{agent.goal}</span>}
              {agent.backstory && <span className="text-[0.625rem] text-(--ui-text-tertiary)">{agent.backstory}</span>}
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

function TaskList({ crew, k }: { crew: CrewDefinition; k: BeholderMessages }) {
  return (
    <Section title={k.tasks}>
      <ol className="flex flex-col gap-1.5">
        {crew.tasks.map((task, index) => (
          <li className="flex flex-col gap-0.5 rounded-[3px] bg-(--ui-bg-quaternary) p-2" key={task.name}>
            <span className="flex items-center gap-1.5 text-xs font-medium">
              <span className="text-(--ui-text-tertiary) tabular-nums">{index + 1}.</span>
              {task.name}
              {task.agent && (
                <Badge size="xs" variant="muted">
                  {task.agent}
                </Badge>
              )}
            </span>
            <span className="text-[0.6875rem] text-(--ui-text-secondary)">{task.description}</span>
            {task.context?.length ? (
              <span className="text-[0.625rem] text-(--ui-text-tertiary)">after: {task.context.join(', ')}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </Section>
  )
}

function Timeline({ events, k }: { events: CrewEvent[]; k: BeholderMessages }) {
  if (!events.length) {
    return <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{k.noEvents}</p>
  }

  return (
    <ol className="beholders-timeline flex max-h-64 flex-col gap-0.5 overflow-y-auto">
      {events.map(event => (
        <li
          className={cn(
            'grid grid-cols-[3.5rem_1fr] items-start gap-2 rounded-[3px] px-1 py-0.5 text-[0.6875rem]',
            event.type.startsWith('crew.task') ? 'text-(--ui-text-secondary)' : 'font-medium'
          )}
          key={event.seq}
        >
          <span className="text-[0.625rem] text-(--ui-text-tertiary) tabular-nums">{event.at.slice(11, 19)}</span>
          <span className="truncate">{describeEvent(event)}</span>
        </li>
      ))}
    </ol>
  )
}

function RunDetail({ runId, k }: { runId: string; k: BeholderMessages }) {
  const { data: run } = useQuery({
    queryFn: () => fetchRunWithNotify(runId),
    queryKey: runKey(runId),
    refetchInterval: query => pollInterval(anyRunning([query.state.data as CrewRunSummary]))
  })

  if (!run) {
    return <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{k.loading}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <StatusBadge k={k} status={run.status} />
        <span className="text-[0.6875rem] text-(--ui-text-tertiary)">{run.id}</span>
        {run.status === 'running' || run.status === 'queued' ? (
          <Button onClick={() => void cancelRun(run.id)} size="xs" variant="text">
            {k.cancelRun}
          </Button>
        ) : null}
      </div>
      {run.result && (
        <div className="flex flex-col gap-1">
          <span className="text-[0.6875rem] font-semibold text-(--ui-text-tertiary) uppercase">{k.result}</span>
          <pre className="max-h-56 overflow-auto rounded-[3px] bg-(--ui-bg-quaternary) p-2 text-[0.6875rem] whitespace-pre-wrap">
            {run.result}
          </pre>
        </div>
      )}
      {run.error && <ErrorState description={run.error} title={k.statusFailed} />}
      <Timeline events={run.events ?? []} k={k} />
    </div>
  )
}

function RunsPanel({ crew, k }: { crew: CrewDefinition; k: BeholderMessages }) {
  const selectedRunId = useValue($selectedRunId)

  const { data: runs } = useQuery({
    queryFn: () => fetchRuns(crew.id),
    queryKey: runsKey(crew.id),
    refetchInterval: query => pollInterval(anyRunning(query.state.data as CrewRunSummary[] | undefined))
  })

  const run = useMutation({
    mutationFn: () => startRun(crew.id, {}),
    onSuccess: summary => {
      $selectedRunId.set(summary.id)
      invalidateAll()
    }
  })

  const activeRunId = selectedRunId || runs?.[0]?.id

  return (
    <Section title={k.runs}>
      <div className="flex items-center gap-2">
        <Button disabled={run.isPending} onClick={() => run.mutate()} size="xs" variant="default">
          <Codicon name="play" size="0.7rem" />
          {k.runCrew}
        </Button>
        {runs?.length ? <span className="text-[0.625rem] text-(--ui-text-tertiary)">{k.runCount(runs.length)}</span> : null}
      </div>

      {run.error && <ErrorState description={(run.error as Error).message} title={k.runCrew} />}

      {runs?.length ? (
        <div className="flex flex-wrap gap-1">
          {runs.map(summary => (
            <button
              className={cn(
                'flex items-center gap-1 rounded-[3px] px-1.5 py-0.5 text-[0.6875rem] transition-colors',
                summary.id === activeRunId ? 'bg-(--chrome-action-hover)' : 'hover:bg-(--chrome-action-hover)'
              )}
              key={summary.id}
              onClick={() => $selectedRunId.set(summary.id)}
              type="button"
            >
              <Badge size="xs" variant={statusTone(summary.status)}>
                {summary.status}
              </Badge>
              <span className="text-(--ui-text-tertiary) tabular-nums">{summary.started_at.slice(11, 19)}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{k.noRuns}</p>
      )}

      {activeRunId && <RunDetail k={k} runId={activeRunId} />}
    </Section>
  )
}

function CrewDetail({ crewId }: { crewId: string }) {
  const k = useBeholderI18n()
  const queryClient = useQueryClient()

  const { data: crew, error } = useQuery({
    queryFn: () => fetchCrew(crewId),
    queryKey: crewKey(crewId)
  })

  const remove = useMutation({
    mutationFn: () => deleteCrew(crewId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: crewKey(crewId) })
      invalidateAll()
    }
  })

  if (error) {
    return <ErrorState description={(error as Error).message} title={k.notReady} />
  }

  if (!crew) {
    return <p className="text-xs text-(--ui-text-tertiary)">{k.loading}</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">{crew.name}</h2>
          <Tip label={k.deleteCrew}>
            <Button disabled={remove.isPending} onClick={() => remove.mutate()} size="icon-xs" variant="ghost">
              <Codicon name="trash" size="0.75rem" />
            </Button>
          </Tip>
        </div>
        {crew.description && <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{crew.description}</p>}
        <p className="text-[0.625rem] text-(--ui-text-tertiary)">
          {crew.process === 'hierarchical' ? k.hierarchical : k.sequential}
        </p>
      </header>
      <AgentList crew={crew} k={k} />
      <TaskList crew={crew} k={k} />
      <RunsPanel crew={crew} k={k} />
    </div>
  )
}

// ------------------------------------------------------------------ the page
export function BeholderPage() {
  const k = useBeholderI18n()
  const selectedCrewId = useValue($selectedCrewId)
  const panel = useValue($panel)

  const { data: crews, error, isLoading } = useQuery({
    queryFn: fetchCrews,
    queryKey: crewsKey(),
    // Nothing changes a crew list except this window; a slow poll keeps a
    // second window (or the CLI) from going stale without a socket.
    refetchInterval: pollInterval(false)
  })

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-(--ui-stroke-secondary) px-4 py-2">
        <div className="min-w-0">
          <h1 className="flex items-center gap-1.5 text-sm font-semibold">
            <Codicon name="organization" size="0.9rem" />
            {k.title}
          </h1>
          <p className="truncate text-[0.6875rem] text-(--ui-text-tertiary)">{k.subtitle}</p>
        </div>
        <Button onClick={() => $panel.set('runs')} size="xs" variant="outline">
          <Codicon name="add" size="0.7rem" />
          {k.newCrew}
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[16rem_1fr]">
        <aside className="flex min-h-0 flex-col gap-1 overflow-y-auto border-r border-(--ui-stroke-secondary) p-2">
          {isLoading && <p className="px-1 text-[0.6875rem] text-(--ui-text-tertiary)">{k.loading}</p>}
          {error && <ErrorState description={(error as Error).message} title={k.notReady} />}
          {crews?.map(crew => (
            <CrewRow crew={crew} key={crew.id} selected={crew.id === selectedCrewId} />
          ))}
          {crews?.length === 0 && !isLoading && (
            <EmptyState description={k.emptyDescription} title={k.emptyTitle} />
          )}
        </aside>

        <main className="min-h-0 overflow-y-auto p-4">
          {panel === 'runs' ? (
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold">{k.blueprints}</h2>
              <NewCrewPanel />
            </div>
          ) : selectedCrewId ? (
            <CrewDetail crewId={selectedCrewId} />
          ) : (
            <EmptyState description={k.noCrewSelected} title={k.title} />
          )}
        </main>
      </div>
    </div>
  )
}
