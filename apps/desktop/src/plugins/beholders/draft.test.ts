import { describe, expect, it } from 'vitest'

import {
  type CrewDraft,
  draftFromBlueprint,
  draftFromCrew,
  draftToInput,
  emptyDraft,
  issueFor,
  placeholdersOf,
  validateDraft
} from './draft'

const BLUEPRINT = {
  agents: [{ goal: 'find', role: 'Researcher' }, { allow_delegation: true, role: 'Writer' }],
  description: 'desc',
  id: 'blueprint.research-desk',
  manager_role: 'Researcher',
  name: 'Research Desk',
  process: 'hierarchical' as const,
  tasks: [
    { agent: 'Researcher', description: 'collect about {topic}', name: 'gather' },
    { agent: 'Writer', context: ['gather'], description: 'write', expected_output: 'notes', name: 'write' }
  ]
}

const valid = (): CrewDraft => ({
  agents: [
    { allow_delegation: false, backstory: '', goal: 'g', role: 'Researcher' },
    { allow_delegation: false, backstory: '', goal: 'g', role: 'Writer' }
  ],
  description: '',
  manager_role: '',
  name: 'Desk',
  process: 'sequential',
  tasks: [{ agent: 'Writer', context: [], description: 'do it', expected_output: '', name: 'work' }]
})

describe('draft shapes', () => {
  it('round-trips a crew through the draft without losing anything', () => {
    const crew = {
      agents: [{ allow_delegation: true, backstory: 'b', goal: 'g', role: 'R' }],
      created_at: 'x',
      description: 'd',
      id: 'crew_1',
      manager_role: '',
      name: 'C',
      process: 'sequential' as const,
      tasks: [{ agent: 'R', context: [], description: 't', expected_output: 'e', name: 'n' }],
      updated_at: 'y'
    }

    expect(draftToInput(draftFromCrew(crew))).toEqual({
      agents: [{ allow_delegation: true, backstory: 'b', goal: 'g', role: 'R' }],
      description: 'd',
      name: 'C',
      process: 'sequential',
      tasks: [{ agent: 'R', context: [], description: 't', expected_output: 'e', name: 'n' }]
    })
  })

  it('starts blank with one agent and one task so it can be filled in', () => {
    const draft = emptyDraft()

    expect(draft.agents).toHaveLength(1)
    expect(draft.tasks).toHaveLength(1)
    expect(draft.process).toBe('sequential')
    // Blank, so it must not validate yet.
    expect(validateDraft(draft).length).toBeGreaterThan(0)
  })

  it('maps a blueprint into a draft field for field', () => {
    const draft = draftFromBlueprint(BLUEPRINT)

    expect(draft.name).toBe('Research Desk')
    expect(draft.process).toBe('hierarchical')
    expect(draft.manager_role).toBe('Researcher')
    expect(draft.agents[1].allow_delegation).toBe(true)
    expect(draft.tasks[1].context).toEqual(['gather'])
  })
})

describe('draftToInput', () => {
  it('trims and omits blank optional fields rather than sending empty strings', () => {
    const input = draftToInput({
      ...valid(),
      description: '   ',
      tasks: [{ agent: '', context: [], description: '  spaced  ', expected_output: '', name: ' work ' }]
    })

    expect(input.name).toBe('Desk')
    expect(input.description).toBeUndefined()
    expect(input.tasks?.[0].name).toBe('work')
    expect(input.tasks?.[0].description).toBe('spaced')
    expect(input.tasks?.[0].agent).toBeUndefined()
    expect(input.tasks?.[0].expected_output).toBeUndefined()
  })

  it('drops context links that name no task', () => {
    const input = draftToInput({
      ...valid(),
      tasks: [
        { agent: '', context: [], description: 'a', expected_output: '', name: 'first' },
        { agent: '', context: ['first', 'ghost'], description: 'b', expected_output: '', name: 'second' }
      ]
    })

    expect(input.tasks?.[1].context).toEqual(['first'])
  })

  it('sends manager_role only for a hierarchical crew that declares one', () => {
    const sequential = draftToInput({ ...valid(), manager_role: 'Researcher' })

    expect(sequential.manager_role).toBeUndefined()

    const hierarchical = draftToInput({ ...valid(), manager_role: 'Researcher', process: 'hierarchical' })

    expect(hierarchical.manager_role).toBe('Researcher')
  })

  it('drops a manager_role that is not an agent, instead of sending it to be rejected', () => {
    const input = draftToInput({ ...valid(), manager_role: 'Ghost', process: 'hierarchical' })

    expect(input.manager_role).toBeUndefined()
  })
})

describe('placeholdersOf', () => {
  it('collects each variable once, in the order it first appears', () => {
    expect(
      placeholdersOf([
        { description: 'about {topic} by {when}' },
        { description: 'more on {topic}' },
        { description: 'no variables here' }
      ])
    ).toEqual(['topic', 'when'])
  })

  it('ignores braces that are not identifiers', () => {
    expect(placeholdersOf([{ description: 'json {"a": 1} and {2bad} and {_ok}' }])).toEqual(['_ok'])
  })

  it('returns nothing for a crew that needs no inputs', () => {
    expect(placeholdersOf([{ description: 'just do it' }])).toEqual([])
  })
})

describe('validateDraft', () => {
  it('accepts a well-formed crew', () => {
    expect(validateDraft(valid())).toEqual([])
  })

  it('requires a name', () => {
    expect(validateDraft({ ...valid(), name: '  ' })).toContainEqual({
      message: 'Give the crew a name.',
      path: 'name'
    })
  })

  it('requires at least one agent and one task', () => {
    const noAgents = validateDraft({ ...valid(), agents: [] })

    expect(noAgents.some(issue => issue.path === 'agents')).toBe(true)

    const noTasks = validateDraft({ ...valid(), tasks: [] })

    expect(noTasks.some(issue => issue.path === 'tasks')).toBe(true)
  })

  it('flags a role with no text', () => {
    const issues = validateDraft({ ...valid(), agents: [{ ...valid().agents[0], role: ' ' }] })

    expect(issueFor(issues, 'agents.0.role')).toBe('Every agent needs a role.')
  })

  it('flags duplicate roles and duplicate task names', () => {
    const issues = validateDraft({
      ...valid(),
      agents: [valid().agents[0], { ...valid().agents[1], role: 'Researcher' }],
      tasks: [valid().tasks[0], valid().tasks[0]]
    })

    expect(issues.map(i => i.message)).toContain('Two agents share the role "Researcher".')
    expect(issues.map(i => i.message)).toContain('Two tasks share the name "work".')
  })

  it('requires a description on every task', () => {
    const issues = validateDraft({ ...valid(), tasks: [{ ...valid().tasks[0], description: ' ' }] })

    expect(issueFor(issues, 'tasks.0.description')).toBe('Task "work" needs a description.')
  })

  it('rejects a task assigned to someone who is not an agent', () => {
    const issues = validateDraft({ ...valid(), tasks: [{ ...valid().tasks[0], agent: 'Ghost' }] })

    expect(issueFor(issues, 'tasks.0.agent')).toContain('not an agent')
  })

  it('rejects a hierarchical manager who is not an agent', () => {
    const issues = validateDraft({ ...valid(), manager_role: 'Ghost', process: 'hierarchical' })

    expect(issueFor(issues, 'manager_role')).toContain('is not an agent')
  })

  it('rejects a hierarchical crew with nobody left to delegate to', () => {
    // One agent, which is also the manager: the engine refuses this.
    const issues = validateDraft({
      ...valid(),
      agents: [valid().agents[0]],
      manager_role: 'Researcher',
      process: 'hierarchical',
      tasks: [{ ...valid().tasks[0], agent: 'Researcher' }]
    })

    expect(issues.map(i => i.message)).toContain(
      'A hierarchical crew needs at least one agent besides its manager.'
    )
  })

  it('allows a hierarchical crew once a second agent exists', () => {
    expect(validateDraft({ ...valid(), manager_role: 'Researcher', process: 'hierarchical' })).toEqual([])
  })
})
