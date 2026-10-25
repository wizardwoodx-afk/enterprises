import { type PluginOs, type PluginRestOptions, type PluginStorage } from '@beyond/plugin-sdk'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  __resetForTests,
  anyRunning,
  bindApi,
  crewsKey,
  deleteCrew,
  describeEvent,
  fetchCrews,
  fetchRunWithNotify,
  mergeEvents,
  pollInterval,
  runKey,
  runsKey,
  startRun,
  statusTone
} from './api'

const storage = (seed: Record<string, unknown> = {}): PluginStorage => ({
  get: <T>(key: string, fallback: T) => (key in seed ? (seed[key] as T) : fallback),
  remove: vi.fn(),
  set: vi.fn()
})

type Call = { path: string; opts?: PluginRestOptions }

function harness(reply: (call: Call) => unknown, seed: Record<string, unknown> = {}) {
  const calls: Call[] = []
  const notify = vi.fn()

  const rest = async <T>(path: string, opts?: PluginRestOptions): Promise<T> => {
    const call = { opts, path }

    calls.push(call)

    return reply(call) as T
  }

  const os = { notify } as unknown as PluginOs
  const dispose = bindApi(rest, storage(seed), () => () => undefined, { os, t: (key: string) => key })

  return { calls, dispose, notify }
}

afterEach(() => {
  __resetForTests()
})

describe('beholders rest contract', () => {
  it('unwraps the crew list envelope', async () => {
    const { calls } = harness(() => ({ crews: [{ id: 'crew_1', name: 'Desk' }], ok: true }))

    await expect(fetchCrews()).resolves.toEqual([{ id: 'crew_1', name: 'Desk' }])
    expect(calls[0]).toEqual({ opts: undefined, path: '/crews' })
  })

  it('starts a run with POST and the inputs body', async () => {
    const { calls } = harness(() => ({ ok: true, run: { id: 'run_1', status: 'queued' } }))

    const run = await startRun('crew_1', { topic: 'tidal' })

    expect(run.id).toBe('run_1')
    expect(calls[0].path).toBe('/crews/crew_1/runs')
    expect(calls[0].opts).toEqual({ body: { inputs: { topic: 'tidal' } }, method: 'POST' })
  })

  it('encodes ids so a hostile crew id cannot address another route', async () => {
    const { calls } = harness(() => ({ ok: true }))

    await deleteCrew('crew/../admin')

    expect(calls[0].path).toBe('/crews/crew%2F..%2Fadmin')
    expect(calls[0].opts).toEqual({ method: 'DELETE' })
  })

  it('asks only for the named crew\u2019s runs', async () => {
    const { calls } = harness(() => ({ ok: true, runs: [] }))

    await fetchRunWithNotify('run_missing').catch(() => undefined)
    expect(calls[0].path).toBe('/runs/run_missing')

  })
})

describe('run notification', () => {
  it('notifies once, and only for a run this session watched working', async () => {
    let status = 'running'

    const { notify } = harness(() => ({
      ok: true,
      run: { crew_id: 'crew_1', crew_name: 'Research Desk', error: '', id: 'run_1', result: 'done', status }
    }))

    await fetchRunWithNotify('run_1')
    expect(notify).not.toHaveBeenCalled()

    status = 'succeeded'

    const finished = await fetchRunWithNotify('run_1')
    expect(finished?.status).toBe('succeeded')
    expect(notify).toHaveBeenCalledTimes(1)

    // A further poll of the same finished run is silent.
    await fetchRunWithNotify('run_1')
    expect(notify).toHaveBeenCalledTimes(1)
  })

  it('does NOT notify for a run that was already finished when opened', async () => {
    const { notify } = harness(() => ({
      ok: true,
      run: { crew_id: 'crew_1', crew_name: 'Old Desk', error: '', id: 'run_1', result: 'done', status: 'succeeded' }
    }))

    await fetchRunWithNotify('run_1')
    expect(notify).not.toHaveBeenCalled()
  })

  it('stays silent when the plugin has no os door', async () => {
    __resetForTests()

    const rest = async <T>(): Promise<T> =>
      ({ ok: true, run: { crew_name: 'x', id: 'run_1', result: '', status: 'running' } }) as T

    bindApi(rest, storage(), () => () => undefined, {
      os: undefined as unknown as PluginOs,
      t: (key: string) => key
    })

    await expect(fetchRunWithNotify('run_1')).resolves.toBeTruthy()
  })
})

describe('cache keys and polling', () => {
  it('scopes crews to the machine, not to a gateway connection', () => {
    expect(crewsKey()).toEqual(['beholders', 'local', 'crews'])
    expect(runsKey('crew_1')).toContain('crew_1')
    expect(runKey('run_1')).toEqual(['beholders', 'local', 'run', 'run_1'])
  })

  it('polls fast only while something is in flight', () => {
    expect(pollInterval(true)).toBe(2_000)
    expect(pollInterval(false)).toBe(15_000)
    expect(anyRunning([{ status: 'succeeded' }] as never)).toBe(false)
    expect(anyRunning([{ status: 'succeeded' }, { status: 'running' }] as never)).toBe(true)
    expect(anyRunning(undefined)).toBe(false)

    // React Query asks for the interval before the first fetch resolves.
    expect(anyRunning([undefined])).toBe(false)
    expect(anyRunning([undefined, { status: 'queued' }] as never)).toBe(true)
  })

  it('maps statuses to badge tones', () => {
    expect(statusTone('succeeded')).toBe('success')
    expect(statusTone('failed')).toBe('destructive')
    expect(statusTone('running')).toBe('warn')
    expect(statusTone('cancelled')).toBe('muted')
  })
})

describe('event merging', () => {
  const event = (seq: number, detail = '') => ({ at: '', seq, type: 'crew.log' as const, detail })

  it('de-duplicates by seq and keeps ascending order', () => {
    const merged = mergeEvents([event(1, 'a'), event(3, 'c')], [event(2, 'b'), event(3, 'c2')])

    expect(merged.map(e => e.seq)).toEqual([1, 2, 3])
    expect(merged[2].detail).toBe('c2')
  })

  it('handles a first batch with no previous cursor', () => {
    expect(mergeEvents(undefined, [event(2), event(1)]).map(e => e.seq)).toEqual([1, 2])
  })

  it('falls back to the raw type for an unknown event', () => {
    expect(describeEvent({ at: '', seq: 1, type: 'crew.mystery' as never })).toBe('crew.mystery')
  })

  it('uses the log detail as the row text', () => {
    expect(describeEvent({ at: '', detail: 'thinking', seq: 1, type: 'crew.log' })).toBe('thinking')
  })
})

describe('persistence', () => {
  let restore: (() => void) | undefined

  beforeEach(() => {
    restore = undefined
  })

  it('restores the last selected crew from storage', async () => {
    const { $selectedCrewId, $panel } = await import('./api')
    const { dispose } = harness(() => ({ ok: true }), { lastCrewId: 'crew_9', panel: 'runs' })

    restore = dispose

    expect($selectedCrewId.get()).toBe('crew_9')
    expect($panel.get()).toBe('runs')

    restore()
  })
})
