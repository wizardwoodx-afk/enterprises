import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { isValidElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { discoverBundledPlugins } from '@/contrib/plugins'
import { $pluginDecisions, $pluginRecords, setPluginEnabled } from '@/contrib/plugins-store'
import { registry } from '@/contrib/registry'
import { SelfFintPage } from '@/plugins/self-fint/page'
import plugin from '@/plugins/self-fint/plugin'

vi.mock('@/contrib/runtime-loader', () => ({ watchRuntimePlugins: vi.fn() }))

/**
 * SelfFint must be a real, first-class part of the app: a route, a sidebar row
 * and palette commands — all discovered by the ordinary bundled-plugin
 * lifecycle, off by default so a user without an ERP site pays nothing.
 */

const source = (area: string) => registry.getArea(area).filter(item => item.source === 'plugin:self-fint')

afterEach(async () => {
  await setPluginEnabled('self-fint', false)
  vi.restoreAllMocks()
})

describe('bundled SelfFint plugin', () => {
  it('declares the identity the docs refer to', () => {
    expect(plugin.id).toBe('self-fint')
    expect(plugin.name).toBe('SelfFint')
    expect(plugin.defaultEnabled).toBe(false)
    expect(plugin.description).toContain('ERPNext')
  })

  it('inventories off by default and contributes nothing until enabled', () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false, 'self-fint': false })

    discoverBundledPlugins()

    expect($pluginRecords.get()['self-fint']).toMatchObject({ kind: 'bundled', status: 'disabled' })
    expect(registry.getArea('routes').some(item => item.source === 'plugin:self-fint')).toBe(false)
  })

  it('registers the page, nav row and palette commands when enabled', async () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false, 'self-fint': false })
    discoverBundledPlugins()

    await setPluginEnabled('self-fint', true)

    expect($pluginRecords.get()['self-fint'].status).toBe('loaded')

    const routes = source('routes')

    expect(routes.some(item => JSON.stringify(item.data).includes('/self-fint'))).toBe(true)

    const nav = source('sidebar.nav')

    expect(nav.some(item => JSON.stringify(item.data).includes('/self-fint'))).toBe(true)

    const paletteIds = source('palette').map(item => (item.data as { id?: string }).id)

    expect(paletteIds).toEqual(expect.arrayContaining(['self-fint.open', 'self-fint.sync']))
  })

  it('withdraws every contribution on disable', async () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false, 'self-fint': false })
    discoverBundledPlugins()
    await setPluginEnabled('self-fint', true)

    expect(source('routes')).toHaveLength(1)

    await setPluginEnabled('self-fint', false)

    for (const area of ['routes', 'sidebar.nav', 'palette']) {
      expect(source(area)).toHaveLength(0)
    }

    expect($pluginDecisions.get()['self-fint']).toBe(false)
  })

  it('mounts the page as a component, never by calling render inline', async () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false, 'self-fint': false })
    discoverBundledPlugins()
    await setPluginEnabled('self-fint', true)

    const route = source('routes')[0]
    const element = route?.render?.()

    expect(isValidElement(element)).toBe(true)
    expect((element as { type: unknown }).type).toBe(SelfFintPage)
  })
})

describe('the plugin ships the files the docs promise', () => {
  it('has an entry point, a page, a data layer and a message bundle', () => {
    const dir = join(process.cwd(), 'src/plugins/self-fint')

    for (const file of ['plugin.tsx', 'page.tsx', 'api.ts', 'i18n.ts']) {
      expect(existsSync(join(dir, file))).toBe(true)
    }
  })
})
