/**
 * The Beholders page: crews on the left, the selected crew on the right.
 *
 * Three panes share the right-hand side — the crew's detail, the new-crew
 * picker, and the editor. They are mutually exclusive views of one selection,
 * so a single atom (`$panel`) drives them rather than nested modals.
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
  ConfirmDialog,
  type CrewBlueprint,
  type CrewDefinition,
  type CrewRun,
  type CrewSummary,
  EmptyState,
  ErrorState,
  Input,
  Tip,
  useMutation,
  useQuery,
  useQueryClient,
  useValue
} from '@beyond/plugin-sdk'
import { useMemo, useState } from 'react'

import {
  $panel,
  $search,
  $selectedCrewId,
  $selectedRunId,
  anyRunning,
  blueprintsKey,
  cancelRun,
  createCrew,
  crewKey,
  crewsKey,
  deleteCrew,
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
  statusTone,
  updateCrew
} from './api'
import {
  type CrewDraft,
  draftFromCrew,
  draftToInput,
  emptyDraft,
  placeholdersOf
} from './draft'
import { CrewEditor } from './editor'
import { type BeholderMessages, useBeholderI18n } from './i18n'
import { RunInputs } from './inputs'
import { formatDuration, Timeline } from './timeline'

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

function Section({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[0.6875rem] font-semibold tracking-wide text-(--ui-text-tertiary) uppercase">{title}</h3>
      {children}
    </section>
  )
}

/** Row-shaped placeholder, so the list does not jump when data lands. */
function ListSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-1">
      {[0, 1, 2].map(row => (
        <div className="flex flex-col gap-1.5 rounded-[3px] px-2 py-1.5" key={row}>
          <div className="h-3 w-2/3 animate-pulse rounded-[2px] bg-(--ui-bg-quaternary)" />
          <div className="h-2.5 w-full animate-pulse rounded-[2px] bg-(--ui-bg-quaternary)" />
          <div className="h-2 w-1/2 animate-pulse rounded-[2px] bg-(--ui-bg-quaternary)" />
        </div>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------- crew row
function CrewRow({ crew, selected }: { crew: CrewSummary; selected: boolean }) {
  return (
    <button
      className={cn(
        'flex w-full flex-col gap-1 rounded-[3px] px-2 py-1.5 text-left transition-colors',
        selected
          ? 'bg-(--chrome-action-hover) text-foreground'
          : 'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover)'
      )}
      onClick={() => {
        $selectedCrewId.set(crew.id)
        $panel.set('detail')
      }}
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

// --------------------------------------------------------------- blueprints
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
      <div className="flex items-center gap-1.5">
        <Button disabled={busy} onClick={() => onUse(blueprint)} size="xs" variant="secondary">
          <Codicon name="add" size="0.7rem" />
          {k.fromBlueprint}
        </Button>
      </div>
    </div>
  )
}

function NewCrewPanel({ onBlank }: { onBlank: () => void }) {
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
      $panel.set('detail')
    }
  })

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold">{k.blueprints}</h2>

      {create.error && <ErrorState description={(create.error as Error).message} title={k.newCrew} />}
      {isLoading && <ListSkeleton />}
      {blueprintsError && <ErrorState description={(blueprintsError as Error).message} title={k.notReady} />}

      {(blueprints ?? []).map(blueprint => (
        <BlueprintCard blueprint={blueprint} busy={create.isPending} key={blueprint.id} onUse={create.mutate} />
      ))}

      <div className="mt-1 flex flex-col gap-1 border-t border-(--ui-stroke-secondary) pt-2">
        <p className="text-[0.625rem] text-(--ui-text-tertiary)">{k.orFromScratch}</p>
        <div>
          <Button onClick={onBlank} size="xs" variant="outline">
            <Codicon name="edit" size="0.7rem" />
            {k.blankCrew}
          </Button>
        </div>
      </div>
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
              {agent.backstory && (
                <span className="text-[0.625rem] text-(--ui-text-tertiary)">{agent.backstory}</span>
              )}
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

function RunDetail({ k, runId }: { k: BeholderMessages; runId: string }) {
  const { data: run } = useQuery({
    queryFn: () => fetchRunWithNotify(runId),
    queryKey: runKey(runId),
    refetchInterval: query => pollInterval(anyRunning([query.state.data]))
  })

  if (!run) {
    return <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{k.loading}</p>
  }

  const live = !['cancelled', 'failed', 'succeeded'].includes(run.status)

  const elapsed =
    run.finished_at && run.started_at
      ? Date.parse(run.finished_at) - Date.parse(run.started_at)
      : undefined

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge k={k} status={run.status} />
        {elapsed !== undefined && elapsed > 0 && (
          <span className="text-[0.625rem] text-(--ui-text-tertiary) tabular-nums">
            {formatDuration(elapsed)}
          </span>
        )}
        <span className="truncate text-[0.625rem] text-(--ui-text-tertiary)">{run.id}</span>
        {live ? (
          <Button onClick={() => void cancelRun(run.id)} size="xs" variant="text">
            {k.cancelRun}
          </Button>
        ) : null}
      </div>

      <Timeline events={run.events ?? []} k={k} live={live} />

      {run.result && (
        <div className="flex flex-col gap-1">
          <span className="text-[0.6875rem] font-semibold text-(--ui-text-tertiary) uppercase">{k.result}</span>
          <pre className="max-h-56 overflow-auto rounded-[3px] bg-(--ui-bg-quaternary) p-2 text-[0.6875rem] whitespace-pre-wrap">
            {run.result}
          </pre>
        </div>
      )}
      {run.error && <ErrorState description={run.error} title={k.statusFailed} />}
    </div>
  )
}

function RunsPanel({ crew, k }: { crew: CrewDefinition; k: BeholderMessages }) {
  const selectedRunId = useValue($selectedRunId)

  const { data: runs } = useQuery({
    queryFn: () => fetchRuns(crew.id),
    queryKey: runsKey(crew.id),
    refetchInterval: query => pollInterval(anyRunning(query.state.data))
  })

  const run = useMutation({
    mutationFn: (values: Record<string, string>) => startRun(crew.id, values),
    onSuccess: summary => {
      $selectedRunId.set(summary.id)
      invalidateAll()
    }
  })

  // `$selectedRunId` is app-wide, so a run picked in ANOTHER crew must not open
  // here: fall back to this crew's newest run.
  const selectedBelongsToCrew = runs?.some(summary => summary.id === selectedRunId) ?? false
  const activeRunId = selectedBelongsToCrew ? selectedRunId : runs?.[0]?.id
  const inputs = placeholdersOf(crew.tasks)

  return (
    <Section title={k.runs}>
      {run.error && <ErrorState description={(run.error as Error).message} title={k.runCrew} />}

      <RunInputs
        inputs={inputs}
        k={k}
        onRun={values => run.mutate(values)}
        running={run.isPending}
      />

      {inputs.length === 0 && (
        <div className="flex items-center gap-2">
          <Button disabled={run.isPending} onClick={() => run.mutate({})} size="xs" variant="default">
            <Codicon name="play" size="0.7rem" />
            {k.runCrew}
          </Button>
          {runs?.length ? (
            <span className="text-[0.625rem] text-(--ui-text-tertiary)">{k.runCount(runs.length)}</span>
          ) : null}
        </div>
      )}

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
              <StatusBadge k={k} status={summary.status} />
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

function CrewDetail({ crewId, onEdit }: { crewId: string; onEdit: (draft: CrewDraft) => void }) {
  const k = useBeholderI18n()
  const queryClient = useQueryClient()
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const { data: crew, error } = useQuery({
    queryFn: () => fetchCrew(crewId),
    queryKey: crewKey(crewId)
  })

  // Deleting a crew is not undoable, so it goes through the shared confirmation
  // dialog rather than firing on the first click of a hover-revealed icon.
  const remove = useMutation({
    mutationFn: () => deleteCrew(crewId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: crewKey(crewId) })
      invalidateAll()
      setConfirmingDelete(false)
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
          <div className="flex items-center gap-0.5">
            <Tip label={k.editCrew}>
              <Button
                aria-label={k.editCrew}
                onClick={() => onEdit(draftFromCrew(crew))}
                size="icon-xs"
                variant="ghost"
              >
                <Codicon name="edit" size="0.75rem" />
              </Button>
            </Tip>
            <Tip label={k.deleteCrew}>
              <Button
                aria-label={k.deleteCrew}
                disabled={remove.isPending}
                onClick={() => setConfirmingDelete(true)}
                size="icon-xs"
                variant="ghost"
              >
                <Codicon name="trash" size="0.75rem" />
              </Button>
            </Tip>
          </div>
          <ConfirmDialog
            confirmLabel={k.deleteCrew}
            description={k.deleteConfirm}
            destructive
            onClose={() => setConfirmingDelete(false)}
            // ConfirmDialog wants a void AsyncFn; the record it returns is not used.
            onConfirm={async () => {
              await remove.mutateAsync()
            }}
            open={confirmingDelete}
            title={crew.name}
          />
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

/** Editor host: saves through the same mutations the picker uses. */
function EditorPanel({ crewId, draft }: { crewId?: string; draft: CrewDraft }) {
  const k = useBeholderI18n()
  const queryClient = useQueryClient()

  const save = useMutation({
    mutationFn: (next: CrewDraft) =>
      crewId ? updateCrew(crewId, draftToInput(next)) : createCrew(draftToInput(next)),
    onSuccess: crew => {
      queryClient.setQueryData(crewKey(crew.id), crew)
      $selectedCrewId.set(crew.id)
      $panel.set('detail')
    }
  })

  return (
    <CrewEditor
      draft={draft}
      error={save.error ? (save.error as Error).message : undefined}
      k={k}
      onCancel={() => $panel.set(crewId ? 'detail' : 'new')}
      onSave={next => save.mutate(next)}
      saving={save.isPending}
      title={crewId ? k.editCrew : k.createCrew}
    />
  )
}

// ------------------------------------------------------------------ the page
export function BeholderPage() {
  const k = useBeholderI18n()
  const selectedCrewId = useValue($selectedCrewId)
  const panel = useValue($panel)
  const search = useValue($search)
  const [draft, setDraft] = useState<CrewDraft>(emptyDraft)

  const { data: crews, error, isLoading } = useQuery({
    queryFn: fetchCrews,
    queryKey: crewsKey(),
    // Nothing changes a crew list except this window; a slow poll keeps a second
    // window (or the CLI) from going stale without a socket.
    refetchInterval: pollInterval(false)
  })

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()

    if (!needle) {
      return crews ?? []
    }

    return (crews ?? []).filter(crew =>
      [crew.name, crew.description, ...crew.roles].some(value => value.toLowerCase().includes(needle))
    )
  }, [crews, search])

  const startBlank = () => {
    setDraft(emptyDraft())
    $panel.set('create')
  }

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
        <Button
          onClick={() => $panel.set('new')}
          size="xs"
          variant={panel === 'new' ? 'secondary' : 'outline'}
        >
          <Codicon name="add" size="0.7rem" />
          {k.newCrew}
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[16rem_1fr]">
        <aside className="flex min-h-0 flex-col gap-1 border-r border-(--ui-stroke-secondary) p-2">
          <Input
            aria-label={k.searchCrews}
            className="mb-1"
            onChange={event => $search.set(event.target.value)}
            placeholder={k.searchCrews}
            value={search}
          />
          <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
            {isLoading && <ListSkeleton />}
            {error && <ErrorState description={(error as Error).message} title={k.notReady} />}
            {visible.map(crew => (
              <CrewRow crew={crew} key={crew.id} selected={crew.id === selectedCrewId && panel === 'detail'} />
            ))}
            {!isLoading && !error && crews?.length === 0 && (
              <EmptyState description={k.emptyDescription} title={k.emptyTitle} />
            )}
            {!isLoading && crews?.length ? (
              visible.length === 0 ? (
                <EmptyState description={k.noMatchesHint(search)} title={k.noMatches} />
              ) : null
            ) : null}
          </div>
        </aside>

        <main className="min-h-0 overflow-y-auto p-4">
          {panel === 'edit' && selectedCrewId ? (
            <EditorPanel crewId={selectedCrewId} draft={draft} />
          ) : panel === 'create' ? (
            <EditorPanel draft={draft} />
          ) : panel === 'new' ? (
            <NewCrewPanel onBlank={startBlank} />
          ) : selectedCrewId ? (
            <CrewDetail
              crewId={selectedCrewId}
              onEdit={next => {
                setDraft(next)
                $panel.set('edit')
              }}
            />
          ) : (
            <EmptyState description={k.noCrewSelected} title={k.title} />
          )}
        </main>
      </div>
    </div>
  )
}
