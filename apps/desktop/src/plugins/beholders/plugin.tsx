/**
 * Beholders — the crew runtime as a first-class Beyond page: `/beholders` with
 * a sidebar row, a ⌘K palette entry, a rebindable "run the selected crew"
 * chord, and a live statusbar count of crews with work in flight. All of it is
 * SDK-consumer work over `ctx.rest` (`/api/plugins/beholders/*`, served by
 * `packages/beholders/src/beholders/service/api.py`). No core edits, no second
 * transport.
 *
 * Ships OFF by default (`defaultEnabled: false`), like kanban: it inventories in
 * Capabilities ▸ Plugins and registers nothing until the user flips the switch.
 * A user who never runs a crew pays nothing for it.
 */

import './beholders.css'

import {
  type BeyondPlugin,
  Codicon,
  host,
  isTerminalRun,
  type KeybindContribution,
  KEYBINDS_AREA,
  PALETTE_AREA,
  type PaletteContribution,
  type RouteContribution,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution,
  STATUSBAR_AREAS,
  Tip,
  useQuery,
  useValue
} from '@beyond/plugin-sdk'

import { $selectedCrewId, anyRunning, bindApi, fetchRuns, pollInterval, runsKey, startRun } from './api'
import { BEHOLDER_LOCALES, useBeholderI18n } from './i18n'
import { BeholderPage } from './page'

/**
 * Statusbar pill: how many of the selected crew's runs are in flight. Hidden
 * when no crew is selected or nothing is running, so the chrome stays quiet on
 * an idle machine.
 *
 * Polls the SAME query key the page does (`runsKey`), so the two share one
 * cache and one request — a statusbar item is a glance, not a monitor, and an
 * idle app must not keep waking the service.
 */
function BeholdersStatus() {
  const k = useBeholderI18n()
  const selected = useValue($selectedCrewId)

  const { data: runs } = useQuery({
    enabled: Boolean(selected),
    queryFn: () => fetchRuns(selected),
    queryKey: runsKey(selected),
    refetchInterval: query => pollInterval(anyRunning(query.state.data))
  })

  const running = runs?.filter(run => !isTerminalRun(run.status)).length ?? 0

  if (!running) {
    return null
  }

  return (
    <Tip label={k.runningCount(running)}>
      <button
        className="inline-flex h-full items-center gap-1 rounded-none px-1.5 text-[0.6875rem] tabular-nums text-(--ui-text-tertiary) transition-colors hover:bg-(--chrome-action-hover) hover:text-foreground"
        onClick={() => host.navigate('/beholders')}
        type="button"
      >
        <Codicon name="organization" size="0.7rem" />
        <span>{k.runningCount(running)}</span>
      </button>
    </Tip>
  )
}

const plugin: BeyondPlugin = {
  defaultEnabled: false,
  description: 'Role-playing agent crews — a /beholders page, a sidebar entry, and a live run count in the status bar.',
  id: 'beholders',
  name: 'Beholders',
  register(ctx) {
    ctx.i18n.register(BEHOLDER_LOCALES)
    ctx.onDispose(bindApi(ctx.rest, ctx.storage, ctx.socket, { os: ctx.os, t: ctx.i18n.t }))

    // ONE action id (`beholders.runCrew`) wired into two areas — a keybind and a
    // palette row that points back at it, so ⌘K shows the live combo. ⌘⌥R /
    // Ctrl+Alt+R keeps the "R for run" mnemonic on a chord core leaves free
    // (`mod+r` and `mod+shift+r` are core built-ins a plugin cannot shadow).
    const runSelected = () => {
      const crewId = $selectedCrewId.get()

      host.navigate('/beholders')

      if (!crewId) {
        return
      }

      void startRun(crewId).catch(() => undefined)
    }

    ctx.registerMany([
      {
        area: ROUTES_AREA,
        data: { path: '/beholders' } satisfies RouteContribution,
        id: 'page',
        render: () => <BeholderPage />
      },
      {
        area: STATUSBAR_AREAS.right,
        id: 'status',
        order: 85,
        render: () => <BeholdersStatus />
      }
    ])

    const registerLabels = () =>
      ctx.registerMany([
        {
          area: SIDEBAR_NAV_AREA,
          data: {
            codicon: 'organization',
            label: ctx.i18n.t('nav'),
            path: '/beholders'
          } satisfies SidebarNavContribution,
          id: 'nav',
          order: 45
        },
        {
          area: PALETTE_AREA,
          data: {
            id: 'beholders.open',
            keywords: ['beholders', 'crew', 'crews', 'agents', 'tasks', 'flows'],
            label: ctx.i18n.t('open'),
            run: () => host.navigate('/beholders')
          } satisfies PaletteContribution,
          id: 'open'
        },
        {
          area: PALETTE_AREA,
          data: {
            action: 'beholders.runCrew',
            id: 'beholders.runCrew',
            keywords: ['beholders', 'crew', 'run', 'kickoff'],
            label: ctx.i18n.t('runCrew'),
            run: runSelected
          } satisfies PaletteContribution,
          id: 'run-crew'
        },
        {
          area: KEYBINDS_AREA,
          data: {
            category: 'view',
            defaults: ['mod+alt+r'],
            id: 'beholders.runCrew',
            label: ctx.i18n.t('runCrew'),
            run: runSelected
          } satisfies KeybindContribution,
          id: 'run-crew'
        }
      ])

    let disposeLabels = registerLabels()

    ctx.i18n.onLocaleChange(() => {
      disposeLabels()
      disposeLabels = registerLabels()
    })
  }
}

export default plugin
