/**
 * SelfFint — the finance pane as a first-class Beyond page: `/self-fint`, a
 * sidebar row, and two palette entries (open, sync now). All of it is ordinary
 * SDK-consumer work over `ctx.rest` (`/api/plugins/self-fint/*`, served by
 * `packages/selffint/src/selffint/asgi.py` mounted by the gateway).
 *
 * No core edits, no second transport. Ships OFF by default (`defaultEnabled:
 * false`), like kanban and Beholders: it inventories in Capabilities ▸ Plugins
 * and registers nothing until the user flips the switch — a user without an
 * ERPNext site pays nothing for it.
 *
 * Note the licence boundary this file sits on the near side of: ERPNext is
 * GPL-3.0 and stays behind HTTP. Nothing here imports or vendors Frappe code.
 */

import {
  type BeyondPlugin,
  host,
  PALETTE_AREA,
  type PaletteContribution,
  type RouteContribution,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution
} from '@beyond/plugin-sdk'

import { bindApi, runSync } from './api'
import { SELF_FINT_LOCALES } from './i18n'
import { SelfFintPage } from './page'

const plugin: BeyondPlugin = {
  defaultEnabled: false,
  description: 'Receivables, GST, input credit and payroll read from your ERPNext site — live or on the demo books.',
  id: 'self-fint',
  name: 'SelfFint',
  register(ctx) {
    ctx.i18n.register(SELF_FINT_LOCALES)
    ctx.onDispose(bindApi(ctx.rest, ctx.storage, ctx.socket, { os: ctx.os, t: ctx.i18n.t }))

    ctx.registerMany([
      {
        area: ROUTES_AREA,
        data: { path: '/self-fint' } satisfies RouteContribution,
        id: 'page',
        render: () => <SelfFintPage />
      }
    ])

    // Labels are re-registered on a locale change: a contribution carries its
    // rendered strings, so a switch mid-session would otherwise leave the
    // sidebar and palette in the old language.
    const registerLabels = () =>
      ctx.registerMany([
        {
          area: SIDEBAR_NAV_AREA,
          data: {
            codicon: 'graph',
            label: ctx.i18n.t('nav'),
            path: '/self-fint'
          } satisfies SidebarNavContribution,
          id: 'nav',
          order: 47
        },
        {
          area: PALETTE_AREA,
          data: {
            id: 'self-fint.open',
            keywords: ['selffint', 'finance', 'erp', 'erpnext', 'invoices', 'gst', 'receivables', 'payroll'],
            label: ctx.i18n.t('open'),
            run: () => host.navigate('/self-fint')
          } satisfies PaletteContribution,
          id: 'open'
        },
        {
          area: PALETTE_AREA,
          data: {
            id: 'self-fint.sync',
            keywords: ['sync', 'refresh', 'erp', 'erpnext', 'books'],
            label: ctx.i18n.t('syncNow'),
            run: () => {
              host.navigate('/self-fint')
              void runSync().catch(() => undefined)
            }
          } satisfies PaletteContribution,
          id: 'sync'
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
