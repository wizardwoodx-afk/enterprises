/**
 * The REAL Beholders page, rendered against a mocked REST layer.
 *
 * Written as an integration test on purpose: the unit tests in `api.test.ts`
 * prove the wire contract, but only a render proves the page composes — the
 * hooks, the i18n bundle, the design-language primitives and the polling
 * wiring. Kanban's board tests set the precedent.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// eslint-disable-next-line no-restricted-imports
import { registerPluginLocales, translatePlugin } from '@/i18n/plugin-i18n'

import type * as BeholdersApi from './api'
import { $panel, $selectedCrewId, $selectedRunId, bindApi } from './api'
import { BEHOLDER_LOCALES } from './i18n'
import { BeholderPage } from './page'

const CREW_SUMMARY = {
  agent_count: 2,
  description: 'scope, gather, write',
  id: 'crew_1',
  name: 'Research Desk',
  process: 'sequential' as const,
  roles: ['Researcher', 'Writer'],
  task_count: 2,
  updated_at: '2026-10-25T06:00:00Z'
}

const CREW = {
  agents: [
    { backstory: 'Patient.', goal: 'Find sources', role: 'Researcher' },
    { allow_delegation: true, goal: 'Write the brief', role: 'Writer' }
  ],
  created_at: '2026-10-25T06:00:00Z',
  description: 'scope, gather, write',
  id: 'crew_1',
  manager_role: 'Researcher',
  name: 'Research Desk',
  process: 'sequential' as const,
  tasks: [
    { agent: 'Researcher', context: [], description: 'collect about {topic}', name: 'gather' },
    { agent: 'Writer', context: ['gather'], description: 'write it up', name: 'write' }
  ],
  updated_at: '2026-10-25T06:00:00Z'
}

const RUN = {
  crew_id: 'crew_1',
  crew_name: 'Research Desk',
  error: '',
  event_count: 3,
  events: [
    { at: '2026-10-25T06:01:00Z', seq: 1, type: 'crew.run.started' as const },
    {
      agent: 'Researcher',
      at: '2026-10-25T06:01:01Z',
      seq: 2,
      task: 'gather',
      type: 'crew.task.completed' as const
    },
    { at: '2026-10-25T06:01:02Z', result: 'the brief', seq: 3, type: 'crew.run.completed' as const }
  ],
  finished_at: '2026-10-25T06:01:02Z',
  id: 'run_1',
  inputs: {},
  result: 'the brief',
  started_at: '2026-10-25T06:01:00Z',
  status: 'succeeded' as const
}

vi.mock('./api', async importOriginal => ({
  ...(await importOriginal<typeof BeholdersApi>()),
  cancelRun: vi.fn(async () => RUN),
  deleteCrew: vi.fn(async () => ({ deleted: 'crew_1', ok: true })),
  fetchCrew: vi.fn(async () => CREW),
  fetchCrews: vi.fn(async () => [CREW_SUMMARY]),
  fetchRunWithNotify: vi.fn(async () => RUN),
  fetchRuns: vi.fn(async () => [{ ...RUN, events: undefined }]),
  invalidateAll: vi.fn(),
  startRun: vi.fn(async () => ({ ...RUN, events: undefined }))
}))

function mount(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  registerPluginLocales('beholders', BEHOLDER_LOCALES)
  bindApi(
    async () => ({ ok: true }) as never,
    { get: <T,>(_k: string, fallback: T) => fallback, remove: vi.fn(), set: vi.fn() },
    () => () => undefined,
    // The module-level translator is what `describeEvent` uses for the timeline,
    // so bind it to the real bundle rather than to the key echo.
    { os: { notify: vi.fn() } as never, t: (key, ...args) => translatePlugin('beholders', 'en', key, args) }
  )
  $selectedCrewId.set('')
  $selectedRunId.set('')
  $panel.set('detail')
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Beholders page', () => {
  it('lists the crews it fetched', async () => {
    mount(<BeholderPage />)

    expect(await screen.findByText('Research Desk')).toBeTruthy()
    expect(screen.getByText('2 agents')).toBeTruthy()
    expect(screen.getByText('2 tasks')).toBeTruthy()
  })

  it('prompts instead of rendering an empty detail pane', async () => {
    mount(<BeholderPage />)

    await screen.findByText('Research Desk')
    expect(screen.getByText('Pick a crew to see its agents, tasks and runs.')).toBeTruthy()
  })

  it('shows the agents, tasks and runs of the selected crew', async () => {
    $selectedCrewId.set('crew_1')
    mount(<BeholderPage />)

    expect(await screen.findByText('Agents')).toBeTruthy()
    expect(screen.getAllByText('Researcher').length).toBeGreaterThan(0)
    // The manager is called out, because it leads rather than working the queue.
    expect(screen.getByText('Manager')).toBeTruthy()
    expect(screen.getByText('gather')).toBeTruthy()
    expect(screen.getByText('after: gather')).toBeTruthy()
    expect(screen.getByText('Run crew')).toBeTruthy()
  })

  it('renders the run timeline and the final result', async () => {
    $selectedCrewId.set('crew_1')
    $selectedRunId.set('run_1')
    mount(<BeholderPage />)

    expect(await screen.findByText('the brief')).toBeTruthy()
    expect(screen.getByText('Run started')).toBeTruthy()
    expect(screen.getByText('Finished gather')).toBeTruthy()
    expect(screen.getByText('Run finished')).toBeTruthy()
  })

  it('starts a run from the button and selects it', async () => {
    $selectedCrewId.set('crew_1')

    const api = await import('./api')

    mount(<BeholderPage />)

    const button = await screen.findByText('Run crew')

    await act(async () => {
      button.closest('button')?.click()
    })

    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith('crew_1', {}))
    await waitFor(() => expect($selectedRunId.get()).toBe('run_1'))
  })

  it('surfaces a service failure as an error instead of an empty list', async () => {
    const api = await import('./api')

    vi.mocked(api.fetchCrews).mockRejectedValueOnce(new Error('Beholders service unreachable'))

    mount(<BeholderPage />)

    expect(await screen.findByText('Beholders service unreachable')).toBeTruthy()
  })

  it('offers the blueprints when the new-crew panel is open', async () => {
    $panel.set('new')
    mount(<BeholderPage />)

    expect(await screen.findByText('Start from a blueprint')).toBeTruthy()
  })
})
