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
  orFromScratch: string
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
  blankCrew: string
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
  // search + list
  searchCrews: string
  noMatches: string
  noMatchesHint: (query: string) => string
  // editor
  createCrew: string
  editCrew: string
  saveCrew: string
  saving: string
  cancel: string
  crewName: string
  crewNameHint: string
  crewDescription: string
  crewDescriptionHint: string
  addAgent: string
  addTask: string
  removeAgent: string
  removeTask: string
  keepOneAgent: string
  agentRole: string
  agentRoleHint: string
  agentGoal: string
  agentGoalHint: string
  agentBackstory: string
  agentBackstoryHint: string
  allowDelegation: string
  taskName: string
  taskNameHint: string
  taskAgent: string
  anyAgent: string
  taskDescription: string
  taskDescriptionHint: string
  taskExpectedOutput: string
  taskExpectedOutputHint: string
  taskContext: string
  placeholdersHint: string
  inputsDetected: string
  unknownAgent: (role: string) => string
  firstAgent: string
  managerHint: string
  fixIssues: (count: number) => string
  // run form
  inputPlaceholder: (name: string) => string
  fillInputs: string
  // run detail
  elapsed: string
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
  blankCrew: 'Start blank',
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
  orFromScratch: 'Or start from scratch',
  process: 'Process',
  result: 'Result',
  runCount: (count: number) => `${count} runs`,
  runCrew: 'Run crew',
  searchCrews: 'Search crews',
  noMatches: 'No crews match',
  noMatchesHint: (query: string) => `Nothing named "${query}".`,
  createCrew: 'New crew',
  editCrew: 'Edit crew',
  saveCrew: 'Save crew',
  saving: 'Saving…',
  cancel: 'Cancel',
  crewName: 'Name',
  crewNameHint: 'Research Desk',
  crewDescription: 'Description',
  crewDescriptionHint: 'What this team is for',
  addAgent: 'Add agent',
  addTask: 'Add task',
  removeAgent: 'Remove agent',
  removeTask: 'Remove task',
  keepOneAgent: 'A crew needs at least one agent.',
  agentRole: 'Role',
  agentRoleHint: 'Researcher',
  agentGoal: 'Goal',
  agentGoalHint: 'What this role is trying to achieve',
  agentBackstory: 'Backstory',
  agentBackstoryHint: 'How this agent thinks and works',
  allowDelegation: 'May hand work to other agents',
  taskName: 'Task',
  taskNameHint: 'gather',
  taskAgent: 'Assigned to',
  anyAgent: 'Let the crew decide',
  taskDescription: 'Instruction',
  taskDescriptionHint: 'Collect evidence about {topic}…',
  taskExpectedOutput: 'Expected output',
  taskExpectedOutputHint: 'A cited evidence list',
  taskContext: 'Uses output from',
  placeholdersHint: 'Wrap a variable in braces — {topic} — to ask for it at run time.',
  inputsDetected: 'This crew asks for',
  unknownAgent: (role: string) => `"${role}" is not an agent of this crew.`,
  firstAgent: 'The first agent leads',
  managerHint: 'The manager delegates; it does not work the queue itself.',
  fixIssues: (count: number) => `${count} ${count === 1 ? 'thing needs' : 'things need'} fixing before this can be saved.`,
  inputPlaceholder: (name: string) => `Value for ${name}`,
  fillInputs: 'Fill every value to run.',
  elapsed: 'elapsed',
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
      addAgent: t('addAgent'),
      addTask: t('addTask'),
      agentBackstory: t('agentBackstory'),
      agentBackstoryHint: t('agentBackstoryHint'),
      agentGoal: t('agentGoal'),
      agentGoalHint: t('agentGoalHint'),
      agentRole: t('agentRole'),
      agentRoleHint: t('agentRoleHint'),
      agents: t('agents'),
      allowDelegation: t('allowDelegation'),
      anyAgent: t('anyAgent'),
      blankCrew: t('blankCrew'),
      blueprints: t('blueprints'),
      cancel: t('cancel'),
      cancelRun: t('cancelRun'),
      createCrew: t('createCrew'),
      crewDescription: t('crewDescription'),
      crewDescriptionHint: t('crewDescriptionHint'),
      crewName: t('crewName'),
      crewNameHint: t('crewNameHint'),
      crews: t('crews'),
      deleteConfirm: t('deleteConfirm'),
      deleteCrew: t('deleteCrew'),
      deleting: t('deleting'),
      editCrew: t('editCrew'),
      elapsed: t('elapsed'),
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
      fillInputs: t('fillInputs'),
      firstAgent: t('firstAgent'),
      fixIssues: (count: number) => t('fixIssues', count),
      fromBlueprint: t('fromBlueprint'),
      hierarchical: t('hierarchical'),
      inputPlaceholder: (name: string) => t('inputPlaceholder', name),
      inputs: t('inputs'),
      inputsDetected: t('inputsDetected'),
      inputsHint: t('inputsHint'),
      keepOneAgent: t('keepOneAgent'),
      loading: t('loading'),
      manager: t('manager'),
      managerHint: t('managerHint'),
      nav: t('nav'),
      newCrew: t('newCrew'),
      noCrewSelected: t('noCrewSelected'),
      noEvents: t('noEvents'),
      noMatches: t('noMatches'),
      noMatchesHint: (query: string) => t('noMatchesHint', query),
      noRuns: t('noRuns'),
      notReady: t('notReady'),
      notify: {
        cancelled: (crew: string) => t('notify.cancelled', crew),
        failed: (crew: string) => t('notify.failed', crew),
        succeeded: (crew: string) => t('notify.succeeded', crew)
      },
      open: t('open'),
      orFromScratch: t('orFromScratch'),
      placeholdersHint: t('placeholdersHint'),
      process: t('process'),
      removeAgent: t('removeAgent'),
      removeTask: t('removeTask'),
      result: t('result'),
      runCount: (count: number) => t('runCount', count),
      runCrew: t('runCrew'),
      runningCount: (count: number) => t('runningCount', count),
      runs: t('runs'),
      saveCrew: t('saveCrew'),
      saving: t('saving'),
      searchCrews: t('searchCrews'),
      sequential: t('sequential'),
      statusCancelled: t('statusCancelled'),
      statusFailed: t('statusFailed'),
      statusQueued: t('statusQueued'),
      statusRunning: t('statusRunning'),
      statusSucceeded: t('statusSucceeded'),
      subtitle: t('subtitle'),
      taskAgent: t('taskAgent'),
      taskContext: t('taskContext'),
      taskDescription: t('taskDescription'),
      taskDescriptionHint: t('taskDescriptionHint'),
      taskExpectedOutput: t('taskExpectedOutput'),
      taskExpectedOutputHint: t('taskExpectedOutputHint'),
      taskName: t('taskName'),
      taskNameHint: t('taskNameHint'),
      tasks: t('tasks'),
      timeline: t('timeline'),
      title: t('title'),
      unknownAgent: (role: string) => t('unknownAgent', role),
    }),
    [t]
  )
}

export type { BeholderMessages }
