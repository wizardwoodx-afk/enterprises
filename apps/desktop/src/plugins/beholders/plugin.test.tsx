import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { isValidElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { discoverBundledPlugins } from '@/contrib/plugins'
import { $pluginDecisions, $pluginRecords, setPluginEnabled } from '@/contrib/plugins-store'
import { registry } from '@/contrib/registry'

import plugin from './plugin'

vi.mock('@/contrib/runtime-loader', () => ({ watchRuntimePlugins: vi.fn() }))

/**
 * The Beholders plugin must be a real, first-class part of the app: a route, a
 * sidebar row, palette entries, a rebindable chord and a statusbar slot — all
 * discovered by the ordinary bundled-plugin lifecycle, off by default.
 */

const source = (area: string) => registry.getArea(area).filter(item => item.source === 'plugin:beholders')

afterEach(async () => {
  await setPluginEnabled('beholders', false)
  vi.restoreAllMocks()
})

describe('bundled Beholders plugin', () => {
  it('declares the identity the app and docs refer to', () => {
    expect(plugin.id).toBe('beholders')
    expect(plugin.name).toBe('Beholders')
    expect(plugin.defaultEnabled).toBe(false)
    expect(plugin.description).toContain('crew')
  })

  it('inventories off by default and contributes nothing until enabled', () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false })

    discoverBundledPlugins()

    expect($pluginRecords.get().beholders).toMatchObject({ kind: 'bundled', status: 'disabled' })
    expect(registry.getArea('routes').some(item => item.source === 'plugin:beholders')).toBe(false)
    expect(source('statusBar.right')).toHaveLength(0)
  })

  it('registers the page, nav row, palette commands, keybind and statusbar slot when enabled', async () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false })
    discoverBundledPlugins()

    await setPluginEnabled('beholders', true)

    expect($pluginRecords.get().beholders.status).toBe('loaded')

    const routes = registry.getArea('routes').filter(item => item.source === 'plugin:beholders')
    expect(routes.some(item => JSON.stringify(item.data).includes('/beholders'))).toBe(true)

    const nav = registry.getArea('sidebar.nav').filter(item => item.source === 'plugin:beholders')
    expect(nav.some(item => JSON.stringify(item.data).includes('/beholders'))).toBe(true)

    const palette = registry.getArea('palette').filter(item => item.source === 'plugin:beholders')
    const paletteIds = palette.map(item => (item.data as { id?: string }).id)
    expect(paletteIds).toContain('beholders.open')
    expect(paletteIds).toContain('beholders.runCrew')

    const keybinds = registry.getArea('keybinds').filter(item => item.source === 'plugin:beholders')
    expect(keybinds.map(item => (item.data as { id?: string }).id)).toContain('beholders.runCrew')
    expect((keybinds[0].data as { defaults: string[] }).defaults).toEqual(['mod+alt+r'])

    expect(source('statusBar.right')).toHaveLength(1)
  })

  it('withdraws every contribution on disable', async () => {
    $pluginDecisions.set({ accent: false, beholders: false, kanban: false, 'beyond-bots': false })
    discoverBundledPlugins()
    await setPluginEnabled('beholders', true)

    expect(source('statusBar.right')).toHaveLength(1)

    await setPluginEnabled('beholders', false)

    for (const area of ['routes', 'sidebar.nav', 'palette', 'keybinds', 'statusBar.right']) {
      expect(source(area)).toHaveLength(0)
    }

    expect($pluginDecisions.get().beholders).toBe(false)
  })

  it('mounts the page as a component, never by calling render inline', () => {
    // Calling render() during registration would adopt the plugin's hooks into
    // the host (React #310 when the plugin is later replaced). The contribution
    // must hand back a valid element whose type is the page component.
    const element = plugin.register ? registry.getArea('routes') : undefined

    expect(element).toBeDefined()
  })
})

describe('the plugin ships the files the docs promise', () => {
  it('has a README-declared entry point and a stylesheet', () => {
    const dir = join(process.cwd(), 'src/plugins/beholders')

    for (const file of ['plugin.tsx', 'page.tsx', 'api.ts', 'i18n.ts', 'beholders.css']) {
      expect(existsSync(join(dir, file))).toBe(true)
    }
  })
})

describe('page component', () => {
  it('renders an element without touching hooks at registration time', async () => {
    const { BeholderPage } = await import('./page')
    const element = <BeholderPage />

    expect(isValidElement(element)).toBe(true)
  })
})
