import assert from 'node:assert/strict'

import { test } from 'vitest'

import { hasWindowsPathPrefix, isExternalVenvHolder, isBeyondOwnedVenvDaemon } from './venv-holder-select'

const SCRIPTS = 'C:\\Beyond\\venv\\Scripts'

test('matches the hindsight daemon shim (exe under venv Scripts + hindsight cmdline)', () => {
  assert.equal(
    isBeyondOwnedVenvDaemon(
      'C:\\Beyond\\venv\\Scripts\\pythonw.exe',
      'C:\\Beyond\\venv\\Scripts\\pythonw.exe -m hindsight_api.main --daemon --idle-timeout 300 --port 9177',
      SCRIPTS
    ),
    true
  )
})

test('Windows path prefix match is ordinal case-insensitive', () => {
  assert.equal(
    isBeyondOwnedVenvDaemon(
      'c:\\beyond\\venv\\scripts\\python.exe',
      'python.exe -m hindsight_api.main --daemon',
      'C:\\Beyond\\venv\\Scripts'
    ),
    true
  )
})

test('excludes external venv holders that are not the hindsight daemon', () => {
  // a user terminal running the beyond CLI from the venv — must NOT be killed
  assert.equal(isBeyondOwnedVenvDaemon('C:\\Beyond\\venv\\Scripts\\beyond.exe', 'beyond chat -q "hi"', SCRIPTS), false)
  // an unrelated python script using the venv interpreter
  assert.equal(
    isBeyondOwnedVenvDaemon('C:\\Beyond\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
})

test('excludes exes outside the venv even when the cmdline mentions hindsight', () => {
  assert.equal(
    isBeyondOwnedVenvDaemon('C:\\Other\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('prefix boundary: sibling dirs (ScriptsX) do not match', () => {
  assert.equal(hasWindowsPathPrefix('C:\\Beyond\\venv\\ScriptsX\\python.exe', SCRIPTS), false)
  assert.equal(hasWindowsPathPrefix('C:\\Beyond\\venv\\Scripts\\python.exe', SCRIPTS), true)
})

test('null/undefined fields never match', () => {
  assert.equal(isBeyondOwnedVenvDaemon(null, 'x', SCRIPTS), false)
  assert.equal(isBeyondOwnedVenvDaemon('C:\\Beyond\\venv\\Scripts\\pythonw.exe', null, SCRIPTS), false)
  assert.equal(isBeyondOwnedVenvDaemon(undefined, undefined, SCRIPTS), false)
})

// --- isExternalVenvHolder (#62311) ------------------------------------------

test('matches the autostart gateway shim (beyond.exe under venv Scripts)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Beyond\\venv\\Scripts\\beyond.exe',
      '"C:\\Beyond\\venv\\Scripts\\beyond.exe" gateway run --external-supervisor',
      SCRIPTS
    ),
    true
  )
})

test('matches the dashboard scheduled task (python -m beyond_cli / -m beyond)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Beyond\\venv\\Scripts\\python.exe',
      '"C:\\Beyond\\venv\\Scripts\\python.exe" -m beyond_cli.main dashboard',
      SCRIPTS
    ),
    true
  )
  assert.equal(
    isExternalVenvHolder('C:\\Beyond\\venv\\Scripts\\pythonw.exe', 'pythonw.exe -m beyond serve', SCRIPTS),
    true
  )
})

test('never matches an unrelated process that merely borrows the venv interpreter', () => {
  // a user's own script running on the venv python — NOT Beyond, must NOT be killed
  assert.equal(
    isExternalVenvHolder('C:\\Beyond\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
  // hindsight daemon is selected by isBeyondOwnedVenvDaemon, not here
  assert.equal(
    isExternalVenvHolder('C:\\Beyond\\venv\\Scripts\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('never matches a process outside the venv, even with beyond in the cmdline', () => {
  // an editor / shell whose command line mentions the install root (#62445 regression guard)
  assert.equal(
    isExternalVenvHolder('C:\\Windows\\System32\\cmd.exe', 'cmd /c cd C:\\Beyond\\venv\\Scripts && dir', SCRIPTS),
    false
  )
  assert.equal(isExternalVenvHolder('C:\\Other\\beyond.exe', 'beyond gateway run', SCRIPTS), false)
})

test('sibling-dir and boundary safety for the external selector', () => {
  assert.equal(isExternalVenvHolder('C:\\Beyond\\venv\\ScriptsX\\beyond.exe', 'beyond gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder(null, 'beyond gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder('C:\\Beyond\\venv\\Scripts\\beyond.exe', null, SCRIPTS), false)
})
