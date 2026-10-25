/**
 * The run form: one field per `{placeholder}` the crew's task descriptions use.
 *
 * Blueprints are written with variables (`Collect evidence about {topic}`), so a
 * crew cannot actually be run without supplying them — before this form existed
 * every run started with an empty input and the agent had to invent the subject.
 * The variables are discovered from the definitions, not declared by hand, so the
 * form appears exactly when a crew needs one.
 */

import { Button, Codicon, Input } from '@beyond/plugin-sdk'
import { useMemo, useState } from 'react'

import type { BeholderMessages } from './i18n'

export function RunInputs({
  inputs,
  k,
  onRun,
  running
}: {
  inputs: string[]
  k: BeholderMessages
  onRun: (values: Record<string, string>) => void
  running: boolean
}) {
  const [values, setValues] = useState<Record<string, string>>({})

  const missing = useMemo(() => inputs.filter(name => !values[name]?.trim()), [inputs, values])
  const ready = missing.length === 0

  if (inputs.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2 rounded-[3px] border border-(--ui-stroke-secondary) p-2">
      <span className="flex items-center gap-1.5 text-[0.6875rem] font-medium text-(--ui-text-secondary)">
        <Codicon name="symbol-variable" size="0.75rem" />
        {k.inputs}
      </span>
      <p className="-mt-1 text-[0.625rem] text-(--ui-text-tertiary)">{k.inputsHint}</p>
      <div className="flex flex-col gap-1.5">
        {inputs.map(name => (
          <label className="grid grid-cols-[max-content_1fr] items-center gap-2" key={name}>
            <code className="rounded-[2px] bg-(--ui-bg-quaternary) px-1 py-0.5 text-[0.625rem] text-(--ui-text-secondary)">
              {name}
            </code>
            <Input
              onChange={event => setValues(current => ({ ...current, [name]: event.target.value }))}
              placeholder={k.inputPlaceholder(name)}
              value={values[name] ?? ''}
            />
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Button
          disabled={running || !ready}
          onClick={() => onRun(Object.fromEntries(inputs.map(name => [name, values[name].trim()])))}
          size="xs"
          variant="default"
        >
          <Codicon name="play" size="0.7rem" />
          {k.runCrew}
        </Button>
        {!ready && <span className="text-[0.625rem] text-(--ui-text-tertiary)">{k.fillInputs}</span>}
      </div>
    </div>
  )
}
