/**
 * The timeline is pure grouping over the event stream, so it is tested directly:
 * the render test in `page.test.tsx` proves it composes, these prove the stages
 * it derives — durations, unfinished tasks and the terminal wording.
 */
import type { CrewEvent } from '@beyond/plugin-sdk'
import { describe, expect, it } from 'vitest'

import { formatDuration, stagesOf } from './timeline'

const at = (seconds: number) => `2026-10-25T06:01:${String(seconds).padStart(2, '0')}Z`

const started: CrewEvent = { at: at(0), seq: 1, type: 'crew.run.started' }

const taskStarted = (task: string, seq: number, second: number): CrewEvent => ({
  agent: 'Researcher',
  at: at(second),
  seq,
  task,
  type: 'crew.task.started'
})

const taskCompleted = (task: string, seq: number, second: number): CrewEvent => ({
  agent: 'Researcher',
  at: at(second),
  seq,
  task,
  type: 'crew.task.completed'
})

const finished: CrewEvent = { at: at(9), result: 'the brief', seq: 9, type: 'crew.run.completed' }

describe('formatDuration', () => {
  it('keeps sub-second work in milliseconds', () => {
    expect(formatDuration(420)).toBe('420ms')
  })

  it('shows tenths under ten seconds and whole seconds above', () => {
    expect(formatDuration(1400)).toBe('1.4s')
    expect(formatDuration(12_400)).toBe('12s')
  })

  it('reads minutes with padded seconds', () => {
    expect(formatDuration(125_000)).toBe('2m 05s')
  })

  it('refuses nonsense rather than printing NaN', () => {
    expect(formatDuration(Number.NaN)).toBe('—')
    expect(formatDuration(-1)).toBe('—')
  })
})

describe('stagesOf', () => {
  it('opens with the run and closes with its terminal event', () => {
    const stages = stagesOf([started, finished])

    expect(stages.map(stage => stage.kind)).toEqual(['start', 'end'])
    expect(stages[1].tone).toBe('success')
  })

  it('measures a task from its started event', () => {
    const stages = stagesOf([started, taskStarted('gather', 2, 1), taskCompleted('gather', 3, 4)])

    expect(stages).toHaveLength(2)
    expect(stages[1]).toMatchObject({ durationMs: 3000, kind: 'task-done', label: 'gather' })
  })

  it('keeps a task that has not finished open', () => {
    const stages = stagesOf([started, taskStarted('gather', 2, 1)])

    expect(stages[1]).toMatchObject({ kind: 'task-start', label: 'gather' })
    expect(stages[1].durationMs).toBeUndefined()
  })

  it('carries the failure message on a failed task', () => {
    const stages = stagesOf([
      started,
      taskStarted('gather', 2, 1),
      { at: at(2), error: 'no sources', seq: 3, task: 'gather', type: 'crew.task.failed' }
    ])

    expect(stages[1]).toMatchObject({ detail: 'no sources', kind: 'task-fail', tone: 'error' })
  })

  it('surfaces the error on a failed run', () => {
    const stages = stagesOf([
      started,
      { at: at(3), error: 'model unavailable', seq: 2, type: 'crew.run.failed' }
    ])

    expect(stages[1]).toMatchObject({ detail: 'model unavailable', kind: 'end', tone: 'error' })
  })

  it('labels a log line with the task it came from', () => {
    const stages = stagesOf([
      started,
      { at: at(1), detail: 'searching', seq: 2, task: 'gather', type: 'crew.log' }
    ])

    expect(stages[1]).toMatchObject({ detail: 'searching', kind: 'log', label: 'gather' })
  })
})
