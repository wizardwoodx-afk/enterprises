import { describe, expect, it } from 'vitest'

import {
  normalizeBeyondOpenString,
  pathFromBeyondDeepLink,
  pathFromOpenDeepLink,
  resolveBeyondOpenPath
} from './beyond-open-target'

describe('normalizeBeyondOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeBeyondOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeBeyondOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped beyond:// deep links to the same path', () => {
    expect(normalizeBeyondOpenString('beyond://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeBeyondOpenString('beyond://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps beyond://open/… deep links by stripping the open host', () => {
    expect(normalizeBeyondOpenString('beyond://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeBeyondOpenString('beyond://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved beyond kinds and unsafe paths', () => {
    expect(normalizeBeyondOpenString('beyond://blueprint/morning-brief')).toBeNull()
    expect(normalizeBeyondOpenString('beyond://plugin/install')).toBeNull()
    expect(normalizeBeyondOpenString('https://example.com/x')).toBeNull()
    expect(normalizeBeyondOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeBeyondOpenString('index-network')).toBeNull()
  })
})

describe('resolveBeyondOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveBeyondOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveBeyondOpenPath({ href: 'beyond://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromBeyondDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromBeyondDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from beyond://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromBeyondDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromBeyondDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromBeyondDeepLink('plugin', 'install')).toBeNull()
  })
})
