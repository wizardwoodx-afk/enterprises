/**
 * The crew editor: name, process, agents and tasks, with inline validation.
 *
 * One component serves both "new crew" and "edit crew" — the only difference is
 * the title and which request saves. The rules live in `draft.ts` (and mirror the
 * server's), so this file is presentation and local list surgery only.
 */

import {
  Badge,
  Button,
  cn,
  Codicon,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  Textarea,
  Tip
} from '@beyond/plugin-sdk'
import { useState } from 'react'

import {
  type AgentDraft,
  type CrewDraft,
  emptyAgent,
  emptyTask,
  issueFor,
  placeholdersOf,
  sectionIssue,
  type TaskDraft,
  validateDraft
} from './draft'
import { type BeholderMessages } from './i18n'

/** A labelled control with its error underneath. */
function Field({
  children,
  error,
  hint,
  label,
  required
}: {
  children: React.ReactNode
  error?: string
  hint?: string
  label: string
  required?: boolean
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="flex items-center gap-1 text-[0.6875rem] font-medium text-(--ui-text-secondary)">
        {label}
        {required && <span className="text-destructive">*</span>}
      </span>
      {children}
      {error ? (
        <span className="text-[0.625rem] text-destructive">{error}</span>
      ) : hint ? (
        <span className="text-[0.625rem] text-(--ui-text-tertiary)">{hint}</span>
      ) : null}
    </label>
  )
}

function RowCard({ children, onRemove, removeLabel }: { children: React.ReactNode; onRemove: () => void; removeLabel: string }) {
  return (
    <div className="relative flex flex-col gap-2 rounded-[3px] border border-(--ui-stroke-secondary) p-2">
      <div className="absolute top-1 right-1">
        <Tip label={removeLabel}>
          <Button onClick={onRemove} size="icon-xs" type="button" variant="ghost">
            <Codicon name="trash" size="0.7rem" />
          </Button>
        </Tip>
      </div>
      {children}
    </div>
  )
}

function AgentRow({
  agent,
  issues,
  index,
  onChange,
  onRemove,
  removable,
  k
}: {
  agent: AgentDraft
  issues: ReturnType<typeof validateDraft>
  index: number
  onChange: (next: AgentDraft) => void
  onRemove: () => void
  removable: boolean
  k: BeholderMessages
}) {
  return (
    <RowCard onRemove={onRemove} removeLabel={k.removeAgent}>
      <div className="flex flex-col gap-2 pr-7">
        <Field
          error={issueFor(issues, `agents.${index}.role`)}
          label={k.agentRole}
          required
        >
          <Input
            onChange={event => onChange({ ...agent, role: event.target.value })}
            placeholder={k.agentRoleHint}
            value={agent.role}
          />
        </Field>
        <Field label={k.agentGoal}>
          <Input
            onChange={event => onChange({ ...agent, goal: event.target.value })}
            placeholder={k.agentGoalHint}
            value={agent.goal}
          />
        </Field>
        <Field label={k.agentBackstory}>
          <Textarea
            onChange={event => onChange({ ...agent, backstory: event.target.value })}
            placeholder={k.agentBackstoryHint}
            rows={2}
            value={agent.backstory}
          />
        </Field>
        <label className="flex items-center gap-2 text-[0.6875rem] text-(--ui-text-secondary)">
          <Switch
            checked={agent.allow_delegation}
            onCheckedChange={checked => onChange({ ...agent, allow_delegation: checked })}
          />
          {k.allowDelegation}
        </label>
      </div>
      {!removable && (
        <span className="text-[0.625rem] text-(--ui-text-tertiary)">{k.keepOneAgent}</span>
      )}
    </RowCard>
  )
}

function TaskRow({
  issues,
  index,
  k,
  onChange,
  onRemove,
  roles,
  siblings,
  task
}: {
  issues: ReturnType<typeof validateDraft>
  index: number
  k: BeholderMessages
  onChange: (next: TaskDraft) => void
  onRemove: () => void
  roles: string[]
  siblings: { name: string }[]
  task: TaskDraft
}) {
  const earlier = siblings.slice(0, index).map(sibling => sibling.name).filter(Boolean)

  const toggleContext = (name: string) =>
    onChange({
      ...task,
      context: task.context.includes(name) ? task.context.filter(item => item !== name) : [...task.context, name]
    })

  return (
    <RowCard onRemove={onRemove} removeLabel={k.removeTask}>
      <div className="flex flex-col gap-2 pr-7">
        <div className="grid grid-cols-2 gap-2">
          <Field error={issueFor(issues, `tasks.${index}.name`)} label={k.taskName} required>
            <Input
              onChange={event => onChange({ ...task, name: event.target.value })}
              placeholder={k.taskNameHint}
              value={task.name}
            />
          </Field>
          <Field label={k.taskAgent}>
            <Select onValueChange={value => onChange({ ...task, agent: value === ANYONE ? '' : value })} value={task.agent || ANYONE}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANYONE}>{k.anyAgent}</SelectItem>
                {roles.filter(Boolean).map(role => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
        <Field
          error={issueFor(issues, `tasks.${index}.description`)}
          hint={k.placeholdersHint}
          label={k.taskDescription}
          required
        >
          <Textarea
            onChange={event => onChange({ ...task, description: event.target.value })}
            placeholder={k.taskDescriptionHint}
            rows={2}
            value={task.description}
          />
        </Field>
        <Field label={k.taskExpectedOutput}>
          <Input
            onChange={event => onChange({ ...task, expected_output: event.target.value })}
            placeholder={k.taskExpectedOutputHint}
            value={task.expected_output}
          />
        </Field>
        {earlier.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[0.625rem] text-(--ui-text-tertiary)">{k.taskContext}:</span>
            {earlier.map(name => (
              <button
                className={cn(
                  'rounded-[3px] px-1.5 py-0.5 text-[0.625rem] transition-colors',
                  task.context.includes(name)
                    ? 'bg-primary/15 text-primary'
                    : 'bg-(--ui-bg-quaternary) text-(--ui-text-tertiary) hover:text-foreground'
                )}
                key={name}
                onClick={() => toggleContext(name)}
                type="button"
              >
                {name}
              </button>
            ))}
          </div>
        )}
        {task.agent && !roles.includes(task.agent) && (
          <span className="text-[0.625rem] text-destructive">{k.unknownAgent(task.agent)}</span>
        )}
      </div>
    </RowCard>
  )
}

/** `<Select>` has no empty value; this stands in for "no agent". */
const ANYONE = '__anyone__'

export function CrewEditor({
  draft: initial,
  k,
  onCancel,
  onSave,
  saving,
  title,
  error
}: {
  draft: CrewDraft
  k: BeholderMessages
  onCancel: () => void
  onSave: (draft: CrewDraft) => void
  saving: boolean
  title: string
  error?: string
}) {
  const [draft, setDraft] = useState<CrewDraft>(initial)
  const [touched, setTouched] = useState(false)

  const issues = validateDraft(draft)
  const roles = draft.agents.map(agent => agent.role.trim())
  const inputs = placeholdersOf(draft.tasks)

  const patch = (next: Partial<CrewDraft>) => setDraft(current => ({ ...current, ...next }))

  const setAgent = (index: number, agent: AgentDraft) =>
    patch({ agents: draft.agents.map((current, i) => (i === index ? agent : current)) })

  const setTask = (index: number, task: TaskDraft) =>
    patch({ tasks: draft.tasks.map((current, i) => (i === index ? task : current)) })

  const submit = () => {
    setTouched(true)

    if (issues.length === 0) {
      onSave(draft)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        <div className="flex items-center gap-1.5">
          <Button onClick={onCancel} size="xs" type="button" variant="text">
            {k.cancel}
          </Button>
          <Button disabled={saving} onClick={submit} size="xs" type="button" variant="default">
            <Codicon name="check" size="0.7rem" />
            {saving ? k.saving : k.saveCrew}
          </Button>
        </div>
      </header>

      {error && <p className="rounded-[3px] bg-destructive/10 px-2 py-1 text-[0.6875rem] text-destructive">{error}</p>}

      {touched && issues.length > 0 && (
        <p className="text-[0.6875rem] text-destructive">{k.fixIssues(issues.length)}</p>
      )}

      <div className="grid grid-cols-2 gap-2">
        <Field error={issueFor(issues, 'name')} label={k.crewName} required>
          <Input onChange={event => patch({ name: event.target.value })} placeholder={k.crewNameHint} value={draft.name} />
        </Field>
        <Field hint={draft.process === 'hierarchical' ? k.managerHint : undefined} label={k.process}>
          <Select
            onValueChange={value => patch({ manager_role: '', process: value as CrewDraft['process'] })}
            value={draft.process}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sequential">{k.sequential}</SelectItem>
              <SelectItem value="hierarchical">{k.hierarchical}</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>

      <Field label={k.crewDescription}>
        <Textarea
          onChange={event => patch({ description: event.target.value })}
          placeholder={k.crewDescriptionHint}
          rows={2}
          value={draft.description}
        />
      </Field>

      {draft.process === 'hierarchical' && (
        <Field error={issueFor(issues, 'manager_role')} hint={k.managerHint} label={k.manager}>
          <Select onValueChange={value => patch({ manager_role: value === ANYONE ? '' : value })} value={draft.manager_role || ANYONE}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANYONE}>{k.firstAgent}</SelectItem>
              {roles.filter(Boolean).map(role => (
                <SelectItem key={role} value={role}>
                  {role}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-[0.6875rem] font-semibold tracking-wide text-(--ui-text-tertiary) uppercase">
            {k.agents}
            <Badge size="xs" variant="muted">
              {draft.agents.length}
            </Badge>
          </h3>
          <Button onClick={() => patch({ agents: [...draft.agents, emptyAgent()] })} size="xs" type="button" variant="text">
            <Codicon name="add" size="0.7rem" />
            {k.addAgent}
          </Button>
        </div>
        {sectionIssue(issues, 'agents') && (
          <p className="text-[0.6875rem] text-destructive">{sectionIssue(issues, 'agents')}</p>
        )}
        {draft.agents.map((agent, index) => (
          <AgentRow
            agent={agent}
            index={index}
            issues={issues}
            k={k}
            key={index}
            onChange={next => setAgent(index, next)}
            onRemove={() => patch({ agents: draft.agents.filter((_, i) => i !== index) })}
            removable={draft.agents.length > 1}
          />
        ))}
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-[0.6875rem] font-semibold tracking-wide text-(--ui-text-tertiary) uppercase">
            {k.tasks}
            <Badge size="xs" variant="muted">
              {draft.tasks.length}
            </Badge>
          </h3>
          <Button onClick={() => patch({ tasks: [...draft.tasks, emptyTask()] })} size="xs" type="button" variant="text">
            <Codicon name="add" size="0.7rem" />
            {k.addTask}
          </Button>
        </div>
        {sectionIssue(issues, 'tasks') && (
          <p className="text-[0.6875rem] text-destructive">{sectionIssue(issues, 'tasks')}</p>
        )}
        {draft.tasks.map((task, index) => (
          <TaskRow
            index={index}
            issues={issues}
            k={k}
            key={index}
            onChange={next => setTask(index, next)}
            onRemove={() => patch({ tasks: draft.tasks.filter((_, i) => i !== index) })}
            roles={roles}
            siblings={draft.tasks}
            task={task}
          />
        ))}
      </section>

      {inputs.length > 0 && (
        <p className="text-[0.625rem] text-(--ui-text-tertiary)">
          {k.inputsDetected}:{' '}
          {inputs.map(name => (
            <code className="mr-1 rounded-[2px] bg-(--ui-bg-quaternary) px-1" key={name}>
              {`{${name}}`}
            </code>
          ))}
        </p>
      )}
    </div>
  )
}
