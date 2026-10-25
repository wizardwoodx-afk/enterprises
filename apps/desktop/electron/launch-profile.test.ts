import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import { createDesktopProfilePreferences } from './desktop-profile'
import { applyLaunchProfileOverride, parseLaunchProfile } from './launch-profile'

function withStoredProfile(profile: string, run: (target: string) => void) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'launch-profile-'))
  const target = path.join(root, 'active-profile.json')
  const preferences = createDesktopProfilePreferences(target)

  try {
    preferences.remember(profile)
    preferences.setDefault({ connectionId: null, profile })
    run(target)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
}

test('parses both --profile spellings and ignores a missing flag', () => {
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile', 'desktop']), 'desktop')
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile=desktop']), 'desktop')
  assert.equal(parseLaunchProfile(['open', '-a', 'Beyond', '--args', '--profile', 'work']), 'work')
  assert.equal(parseLaunchProfile(['Beyond.exe', '--local']), null)
  assert.equal(parseLaunchProfile(['Beyond.exe']), null)
})

test('normalizes a launch profile the same way the CLI does', () => {
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile', '  Desktop  ']), 'desktop')
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile=Work']), 'work')
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile', 'default']), 'default')
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile']), null)
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile=']), null)
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile', 'my profile']), null)
  assert.equal(parseLaunchProfile(['Beyond.exe', '--profile', '-desktop']), null)
})

test('a launch --profile is persisted before the backend reads active-profile.json', () => {
  withStoredProfile('stored', target => {
    const preferences = createDesktopProfilePreferences(target)

    const launched = applyLaunchProfileOverride(['Beyond.exe', '--profile', 'desktop'], name => {
      preferences.remember(name)
    })

    const restarted = createDesktopProfilePreferences(target)

    assert.equal(launched, 'desktop')
    assert.equal(restarted.readActive(), 'desktop')
    assert.deepEqual(restarted.getDefault(), { connectionId: null, profile: 'stored' })
  })
})

test('--profile=<name> persists the same profile the space spelling does', () => {
  withStoredProfile('stored', target => {
    const preferences = createDesktopProfilePreferences(target)

    applyLaunchProfileOverride(['Beyond.exe', '--ozone-platform=wayland', '--profile=desktop'], name => {
      preferences.remember(name)
    })

    assert.equal(createDesktopProfilePreferences(target).readActive(), 'desktop')
  })
})

test('a missing or invalid flag does not change the stored profile', () => {
  for (const argv of [
    ['Beyond.exe'],
    ['Beyond.exe', '--local'],
    ['Beyond.exe', '--profile'],
    ['Beyond.exe', '--profile', 'Not a name'],
    ['Beyond.exe', '--profile=../desktop']
  ]) {
    withStoredProfile('stored', target => {
      const before = fs.readFileSync(target, 'utf8')
      let persisted = false

      const launched = applyLaunchProfileOverride(argv, () => {
        persisted = true
      })

      assert.equal(launched, null)
      assert.equal(persisted, false)
      assert.equal(fs.readFileSync(target, 'utf8'), before)
    })
  }
})
