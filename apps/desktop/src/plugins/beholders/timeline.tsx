/**
 * The run timeline.
 *
 * A crew run is a sequence of task boundaries, so the timeline reads as stages
 * with a duration each, not as a log of equal-weight lines. Durations come from
 * the `at` stamps the service records, which is why every event carries one.
 */

import { Badge, cn, Codicon } from '@beyond/plugin-sdk'
import type { CrewEvent } from '@beyond/plugin-sdk'
import { useEffect, useRef } from 'react'

import type { BeholderMessages } from './i18n'

const TERMINAL = new Set(['crew.run.cancelled', 'crew.run.completed', 'crew.run.failed'])

/** `1.4s` / `12s` / `2m 05s` — short enough to sit in a row. */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) {
    return '—'
  }

  if (ms < 1000) {
    return `${Math.round(ms)}ms`
  }

  const seconds = ms / 1000

  if (seconds < 60) {
    return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`
  }

  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)

  return `${minutes}m ${String(rest).padStart(2, '0')}s`
}

export interface Stage {
  /** Task name, or the run's own marker for the start/end rows. */
  key: string
  /** What happened, so the row can be worded rather than just named. */
  kind: 'end' | 'log' | 'start' | 'task-done' | 'task-fail' | 'task-start'
  label: string
  at: string
  durationMs?: number
  tone: 'error' | 'info' | 'muted' | 'success'
  /** Free text under the label: an error, a summary, a log line. */
  detail?: string
}

/** Group raw events into one row per task boundary, with durations. */
export function stagesOf(events: readonly CrewEvent[]): Stage[] {
  const stages: Stage[] = []
  const open = new Map<string, number>()

  const ms = (at: string) => Date.parse(at)

  for (const event of events) {
    const at = ms(event.at)

    if (event.type === 'crew.run.started') {
      stages.push({ at: event.at, key: 'start', kind: 'start', label: 'start', tone: 'info' })

      continue
    }

    if (event.type === 'crew.task.started' && event.task) {
      open.set(event.task, at)

      continue
    }

    if (event.type === 'crew.task.completed' && event.task) {
      const startedAt = open.get(event.task)

      open.delete(event.task)
      stages.push({
        at: event.at,
        durationMs: startedAt === undefined ? undefined : at - startedAt,
        key: `task:${event.task}`,
        kind: 'task-done',
        label: event.task,
        tone: 'success'
      })

      continue
    }

    if (event.type === 'crew.task.failed' && event.task) {
      open.delete(event.task)
      stages.push({
        at: event.at,
        key: `task:${event.task}`,
        kind: 'task-fail',
        label: event.task,
        tone: 'error',
        ...(event.error ? { detail: event.error } : {})
      })

      continue
    }

    if (TERMINAL.has(event.type)) {
      stages.push({
        at: event.at,
        detail: event.error || event.reason,
        key: 'end',
        kind: 'end',
        label: event.type === 'crew.run.completed' ? 'done' : event.type.split('.').pop() ?? 'end',
        tone: event.type === 'crew.run.completed' ? 'success' : event.type === 'crew.run.failed' ? 'error' : 'muted'
      })

      continue
    }

    if (event.type === 'crew.log' && event.detail) {
      stages.push({
        at: event.at,
        detail: event.detail,
        key: `log:${event.seq}`,
        kind: 'log',
        label: event.task || 'log',
        tone: 'muted'
      })
    }
  }

  // A task that is still running has no closing event yet.
  for (const [task, startedAt] of open) {
    stages.push({ at: events.at(-1)?.at ?? '', key: `open:${task}`, kind: 'task-start', label: task, tone: 'info' })
    void startedAt
  }

  return stages
}

const TONE_CLASS = {
  error: 'text-destructive',
  info: 'text-(--ui-text-secondary)',
  muted: 'text-(--ui-text-tertiary)',
  success: 'text-(--ui-text-primary)'
} as const

const TONE_ICON = {
  error: 'error',
  info: 'loading',
  muted: 'circle-outline',
  success: 'pass-filled'
} as const

export function Timeline({ events, k, live }: { events: CrewEvent[]; k: BeholderMessages; live: boolean }) {
  const scroller = useRef<HTMLOListElement>(null)

  // Follow the run: a live timeline that does not scroll to the newest stage is
  // a scrollbar the user has to chase.
  useEffect(() => {
    if (live && scroller.current) {
      scroller.current.scrollTop = scroller.current.scrollHeight
    }
  }, [events.length, live])

  if (!events.length) {
    return <p className="text-[0.6875rem] text-(--ui-text-tertiary)">{k.noEvents}</p>
  }

  const stages = stagesOf(events)

  // A row says what happened, not just where it happened: "Finished gather" is
  // readable at a glance; "gather" with a tick beside it is not.
  const wording = (stage: Stage): string => {
    switch (stage.kind) {
      case 'start':
        return k.event.runStarted

      case 'task-start':
        return k.event.taskStarted(stage.label)

      case 'task-done':
        return k.event.taskCompleted(stage.label)

      case 'task-fail':
        return k.event.taskFailed(stage.label)

      case 'end':
        return stage.tone === 'success'
          ? k.event.runCompleted
          : stage.tone === 'error'
            ? k.event.runFailed(stage.detail ?? '')
            : k.event.runCancelled

      default:
        return stage.label
    }
  }

  return (
    <ol className="beholders-timeline flex max-h-64 flex-col gap-0.5 overflow-y-auto" ref={scroller}>
      {stages.map(stage => (
        <li className="grid grid-cols-[0.75rem_1fr_max-content] items-start gap-2 px-1 py-0.5" key={stage.key}>
          <Codicon className={cn('mt-0.5', TONE_CLASS[stage.tone])} name={TONE_ICON[stage.tone]} size="0.65rem" />
          <span className="flex min-w-0 flex-col">
            <span className={cn('truncate text-[0.6875rem]', TONE_CLASS[stage.tone])}>
              {wording(stage)}
            </span>
            {stage.detail && (
              <span className="truncate text-[0.625rem] text-(--ui-text-tertiary)">{stage.detail}</span>
            )}
          </span>
          <span className="text-[0.625rem] text-(--ui-text-tertiary) tabular-nums">
            {stage.durationMs === undefined ? stage.at.slice(11, 19) : formatDuration(stage.durationMs)}
          </span>
        </li>
      ))}
      {live && (
        <li className="flex items-center gap-1.5 px-1 py-0.5 text-[0.625rem] text-(--ui-text-tertiary)">
          <Codicon name="loading" size="0.65rem" />
          {k.event.log}
        </li>
      )}
      {stages.length === 0 && <li className="px-1 text-[0.6875rem] text-(--ui-text-tertiary)">{k.noEvents}</li>}
    </ol>
  )
}

export { Badge }
