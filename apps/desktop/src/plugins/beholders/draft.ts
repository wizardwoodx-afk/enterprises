/**
 * The editable form of a crew, and the rules that decide whether it may be saved.
 *
 * A `CrewDraft` is what the editor holds while the user types — strings for
 * everything, including the fields the wire models as tuples, because a
 * half-typed task must not crash a renderer. `draftToInput` is the single place
 * that turns it back into the wire shape.
 *
 * The validation here deliberately mirrors `CrewDefinition.from_dict` in
 * `packages/beholders/src/beholders/service/models.py`, field for field and rule
 * for rule. The server is still the authority (it must be — the CLI and the RPC
 * door share it), but a user who types a bad crew should learn that from the
 * form, not from a red banner after a round-trip.
 */
import type { CrewBlueprint, CrewDefinition, CrewInput, CrewProcess } from '@beyond/plugin-sdk'

export interface AgentDraft {
  role: string
  goal: string
  backstory: string
  allow_delegation: boolean
}

export interface TaskDraft {
  name: string
  description: string
  expected_output: string
  /** Empty means "the crew decides who runs it". */
  agent: string
  /** Names of earlier tasks this one consumes. */
  context: string[]
}

export interface CrewDraft {
  name: string
  description: string
  process: CrewProcess
  /** Only meaningful for `hierarchical`; empty means "the first agent leads". */
  manager_role: string
  agents: AgentDraft[]
  tasks: TaskDraft[]
}

/** A field path a validation message can point at, e.g. `agents.0.role`. */
export type DraftIssue = { path: string; message: string }

const PLACEHOLDER = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g

export function emptyAgent(): AgentDraft {
  return { allow_delegation: false, backstory: '', goal: '', role: '' }
}

export function emptyTask(): TaskDraft {
  return { agent: '', context: [], description: '', expected_output: '', name: '' }
}

/** A blank crew with one agent and one task — enough to be valid once filled. */
export function emptyDraft(): CrewDraft {
  return {
    agents: [emptyAgent()],
    description: '',
    manager_role: '',
    name: '',
    process: 'sequential',
    tasks: [emptyTask()]
  }
}

export function draftFromBlueprint(blueprint: CrewBlueprint): CrewDraft {
  return {
    agents: blueprint.agents.map(agent => ({
      allow_delegation: Boolean(agent.allow_delegation),
      backstory: agent.backstory ?? '',
      goal: agent.goal ?? '',
      role: agent.role
    })),
    description: blueprint.description ?? '',
    manager_role: blueprint.manager_role ?? '',
    name: blueprint.name,
    process: blueprint.process,
    tasks: blueprint.tasks.map(task => ({
      agent: task.agent ?? '',
      context: [...(task.context ?? [])],
      description: task.description,
      expected_output: task.expected_output ?? '',
      name: task.name
    }))
  }
}

export function draftFromCrew(crew: CrewDefinition): CrewDraft {
  return {
    agents: crew.agents.map(agent => ({
      allow_delegation: Boolean(agent.allow_delegation),
      backstory: agent.backstory ?? '',
      goal: agent.goal ?? '',
      role: agent.role
    })),
    description: crew.description ?? '',
    manager_role: crew.manager_role ?? '',
    name: crew.name,
    process: crew.process,
    tasks: crew.tasks.map(task => ({
      agent: task.agent ?? '',
      context: [...(task.context ?? [])],
      description: task.description,
      expected_output: task.expected_output ?? '',
      name: task.name
    }))
  }
}

/** Trim every string, drop blank context links, and emit only wire fields. */
export function draftToInput(draft: CrewDraft): CrewInput {
  const roles = draft.agents.map(agent => agent.role.trim())
  const taskNames = new Set(draft.tasks.map(task => task.name.trim()).filter(Boolean))

  return {
    agents: draft.agents.map(agent => ({
      allow_delegation: agent.allow_delegation,
      ...(agent.backstory.trim() ? { backstory: agent.backstory.trim() } : {}),
      ...(agent.goal.trim() ? { goal: agent.goal.trim() } : {}),
      role: agent.role.trim()
    })),
    ...(draft.description.trim() ? { description: draft.description.trim() } : {}),
    // Only send a manager the crew actually declares; the server rejects the rest.
    ...(draft.process === 'hierarchical' && roles.includes(draft.manager_role.trim())
      ? { manager_role: draft.manager_role.trim() }
      : {}),
    name: draft.name.trim(),
    process: draft.process,
    tasks: draft.tasks.map(task => ({
      ...(task.agent.trim() ? { agent: task.agent.trim() } : {}),
      context: task.context.filter(name => taskNames.has(name)),
      description: task.description.trim(),
      ...(task.expected_output.trim() ? { expected_output: task.expected_output.trim() } : {}),
      name: task.name.trim()
    }))
  }
}

/**
 * Every `{name}` a task description references, in first-seen order.
 *
 * These are the run's inputs: the runner fills them before kickoff. Scanning the
 * descriptions (rather than asking the user to declare variables) means the
 * inputs form appears exactly when the crew needs one.
 */
export function placeholdersOf(tasks: readonly { description: string }[]): string[] {
  const seen: string[] = []

  for (const task of tasks) {
    for (const match of task.description.matchAll(PLACEHOLDER)) {
      if (!seen.includes(match[1])) {
        seen.push(match[1])
      }
    }
  }

  return seen
}

/** Rules `CrewDefinition.from_dict` enforces, checked locally and in order. */
export function validateDraft(draft: CrewDraft): DraftIssue[] {
  const issues: DraftIssue[] = []

  if (!draft.name.trim()) {
    issues.push({ message: 'Give the crew a name.', path: 'name' })
  }

  const roles = draft.agents.map(agent => agent.role.trim())

  if (!roles.some(Boolean)) {
    issues.push({ message: 'A crew needs at least one agent.', path: 'agents' })
  }

  const duplicates = roles.filter((role, index) => role && roles.indexOf(role) !== index)

  if (duplicates.length) {
    issues.push({ message: `Two agents share the role "${duplicates[0]}".`, path: 'agents' })
  }

  draft.agents.forEach((agent, index) => {
    if (!agent.role.trim()) {
      issues.push({ message: 'Every agent needs a role.', path: `agents.${index}.role` })
    }
  })

  const taskNames = draft.tasks.map(task => task.name.trim())

  if (!taskNames.some(Boolean)) {
    issues.push({ message: 'A crew needs at least one task.', path: 'tasks' })
  }

  const duplicateTasks = taskNames.filter((name, index) => name && taskNames.indexOf(name) !== index)

  if (duplicateTasks.length) {
    issues.push({ message: `Two tasks share the name "${duplicateTasks[0]}".`, path: 'tasks' })
  }

  draft.tasks.forEach((task, index) => {
    if (!task.name.trim()) {
      issues.push({ message: 'Every task needs a name.', path: `tasks.${index}.name` })
    }

    if (!task.description.trim()) {
      issues.push({ message: `Task "${task.name.trim() || index + 1}" needs a description.`, path: `tasks.${index}.description` })
    }

    if (task.agent.trim() && !roles.includes(task.agent.trim())) {
      issues.push({
        message: `Task "${task.name.trim() || index + 1}" is assigned to "${task.agent.trim()}", which is not an agent.`,
        path: `tasks.${index}.agent`
      })
    }
  })

  if (draft.process === 'hierarchical') {
    const manager = draft.manager_role.trim()

    if (manager && !roles.includes(manager)) {
      issues.push({ message: `The manager "${manager}" is not an agent of this crew.`, path: 'manager_role' })
    }

    // The engine refuses a hierarchical crew whose lead is also a worker, and a
    // crew with no workers left. Catch both here rather than after a round-trip.
    const workers = roles.filter(role => role && role !== (manager || roles[0]))

    if (roles.some(Boolean) && !workers.length) {
      issues.push({
        message: 'A hierarchical crew needs at least one agent besides its manager.',
        path: 'agents'
      })
    }
  }

  return issues
}

/** The message for one field, or `undefined`. Editor rows render this inline. */
export function issueFor(issues: readonly DraftIssue[], path: string): string | undefined {
  return issues.find(issue => issue.path === path)?.message
}

/** The first blocking message in a section (`agents`, `tasks`, …). */
export function sectionIssue(issues: readonly DraftIssue[], section: string): string | undefined {
  return issues.find(issue => issue.path === section || issue.path.startsWith(`${section}.`))?.message
}
