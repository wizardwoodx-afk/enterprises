/**
 * Plugin-scoped i18n for Beholders — bundles ship under the plugin id via
 * `ctx.i18n.register`, never touching core en.ts. `useBeholderI18n()` binds the
 * translator to the message SHAPE so components keep typed access, while the
 * module-level `t` in `api.ts` stays stringly for non-React code.
 *
 * Parameterised entries are functions: `t('event.taskStarted', name)` calls the
 * function with positional args.
 */

import { type PluginLocaleBundles, usePluginI18n } from '@beyond/plugin-sdk'
import { useMemo } from 'react'

type BeholderMessages = {
  nav: string
  open: string
  newCrew: string
  runCrew: string
  cancelRun: string
  title: string
  subtitle: string
  emptyTitle: string
  emptyDescription: string
  noCrewSelected: string
  notReady: string
  loading: string
  crews: string
  runs: string
  blueprints: string
  fromBlueprint: string
  deleteCrew: string
  deleteConfirm: string
  deleting: string
  agents: string
  tasks: string
  process: string
  manager: string
  sequential: string
  hierarchical: string
  inputs: string
  inputsHint: string
  result: string
  timeline: string
  noRuns: string
  noEvents: string
  statusQueued: string
  statusRunning: string
  statusSucceeded: string
  statusFailed: string
  statusCancelled: string
  runCount: (count: number) => string
  runningCount: (count: number) => string
  notify: { succeeded: (crew: string) => string; failed: (crew: string) => string; cancelled: (crew: string) => string }
  event: {
    runStarted: string
    taskStarted: (task: string) => string
    taskCompleted: (task: string) => string
    taskFailed: (task: string) => string
    runCompleted: string
    runFailed: (error: string) => string
    runCancelled: string
    log: string
  }
}

const EN: BeholderMessages = {
  agents: 'Agents',
  blueprints: 'Start from a blueprint',
  cancelRun: 'Stop',
  crews: 'Crews',
  deleteConfirm: 'Delete this crew? Its run history stays in the log.',
  deleteCrew: 'Delete crew',
  deleting: 'Deleting…',
  emptyDescription: 'A crew is a team of role-playing agents working through a list of tasks.',
  emptyTitle: 'No crews yet',
  event: {
    log: 'Working…',
    runCancelled: 'Run stopped',
    runCompleted: 'Run finished',
    runFailed: (error: string) => `Run failed: ${error}`,
    runStarted: 'Run started',
    taskCompleted: (task: string) => `Finished ${task}`,
    taskFailed: (task: string) => `Failed ${task}`,
    taskStarted: (task: string) => `Started ${task}`
  },
  fromBlueprint: 'Use this blueprint',
  hierarchical: 'Hierarchical — a lead delegates',
  inputs: 'Inputs',
  inputsHint: 'Values for the {placeholders} in the task descriptions.',
  loading: 'Loading…',
  manager: 'Manager',
  nav: 'Beholders',
  newCrew: 'New crew',
  noCrewSelected: 'Pick a crew to see its agents, tasks and runs.',
  noEvents: 'Nothing yet — start a run.',
  noRuns: 'This crew has not run yet.',
  notReady: 'The Beholders service is not connected.',
  notify: {
    cancelled: (crew: string) => `${crew} run stopped`,
    failed: (crew: string) => `${crew} run failed`,
    succeeded: (crew: string) => `${crew} run finished`
  },
  open: 'Open Beholders',
  process: 'Process',
  result: 'Result',
  runCount: (count: number) => `${count} runs`,
  runCrew: 'Run crew',
  runningCount: (count: number) => `${count} running`,
  runs: 'Runs',
  sequential: 'Sequential — one task at a time',
  statusCancelled: 'stopped',
  statusFailed: 'failed',
  statusQueued: 'queued',
  statusRunning: 'running',
  statusSucceeded: 'done',
  subtitle: 'Agents, tasks and crews — running natively in Beyond.',
  tasks: 'Tasks',
  timeline: 'Timeline',
  title: 'Beholders'
}

export const BEHOLDER_LOCALES: PluginLocaleBundles = { en: EN }

/** Typed translator bound to the message shape.
 *
 *  Built explicitly rather than by walking the English catalog: the returned
 *  object is what `tsc` checks against `BeholderMessages`, so a key renamed here
 *  and not in the bundle (or vice versa) fails the build instead of silently
 *  rendering the key text. */
export function useBeholderI18n(): BeholderMessages {
  const t = usePluginI18n('beholders')

  return useMemo(
    () => ({
      agents: t('agents'),
      blueprints: t('blueprints'),
      cancelRun: t('cancelRun'),
      crews: t('crews'),
      deleteConfirm: t('deleteConfirm'),
      deleteCrew: t('deleteCrew'),
      deleting: t('deleting'),
      emptyDescription: t('emptyDescription'),
      emptyTitle: t('emptyTitle'),
      event: {
        log: t('event.log'),
        runCancelled: t('event.runCancelled'),
        runCompleted: t('event.runCompleted'),
        runFailed: (error: string) => t('event.runFailed', error),
        runStarted: t('event.runStarted'),
        taskCompleted: (task: string) => t('event.taskCompleted', task),
        taskFailed: (task: string) => t('event.taskFailed', task),
        taskStarted: (task: string) => t('event.taskStarted', task)
      },
      fromBlueprint: t('fromBlueprint'),
      hierarchical: t('hierarchical'),
      inputs: t('inputs'),
      inputsHint: t('inputsHint'),
      loading: t('loading'),
      manager: t('manager'),
      nav: t('nav'),
      newCrew: t('newCrew'),
      noCrewSelected: t('noCrewSelected'),
      noEvents: t('noEvents'),
      noRuns: t('noRuns'),
      notReady: t('notReady'),
      notify: {
        cancelled: (crew: string) => t('notify.cancelled', crew),
        failed: (crew: string) => t('notify.failed', crew),
        succeeded: (crew: string) => t('notify.succeeded', crew)
      },
      open: t('open'),
      process: t('process'),
      result: t('result'),
      runCount: (count: number) => t('runCount', count),
      runCrew: t('runCrew'),
      runningCount: (count: number) => t('runningCount', count),
      runs: t('runs'),
      sequential: t('sequential'),
      statusCancelled: t('statusCancelled'),
      statusFailed: t('statusFailed'),
      statusQueued: t('statusQueued'),
      statusRunning: t('statusRunning'),
      statusSucceeded: t('statusSucceeded'),
      subtitle: t('subtitle'),
      tasks: t('tasks'),
      timeline: t('timeline'),
      title: t('title')
    }),
    [t]
  )
}

export type { BeholderMessages }
