import type { ReactNode } from 'react'

/**
 * idle      未選
 * selected  已選、尚未批改（中性藍，不是綠色）
 * correct   批改後：正確答案
 * wrong     批改後：使用者選了且答錯
 * disabled  不可作答
 */
export type ChoiceState = 'idle' | 'selected' | 'correct' | 'wrong' | 'disabled'

interface ChoiceOptionBaseProps {
  /** Option letter shown in the badge, e.g. 'A'. */
  letter: string
  /** Option text. */
  children: ReactNode
  /** Explicit visual state. If omitted: disabled → 'disabled', checked/selected → 'selected', else 'idle'. */
  state?: ChoiceState
  /** Content under the text (option images etc.). */
  after?: ReactNode
  /** Screen-reader suffix for graded states; defaults to 「正確答案」/「你的答案（答錯）」. */
  statusLabel?: string
  describedBy?: string
  className?: string
}

export interface ChoiceOptionRadioProps extends ChoiceOptionBaseProps {
  /** Exam mode: native radio in a <label>; group the options in role="radiogroup" or a <fieldset>. */
  kind: 'radio'
  name: string
  value: string
  checked: boolean
  /** Fires from the radio's onChange only (label clicks are forwarded by the browser; no double-fire). */
  onChange: (value: string) => void
  disabled?: boolean
}

export interface ChoiceOptionButtonProps extends ChoiceOptionBaseProps {
  /** Practice mode: <button aria-pressed>. */
  kind: 'button'
  selected: boolean
  onSelect: () => void
  /** After answering: keeps focusable but ignores clicks (aria-disabled). */
  locked?: boolean
}

export type ChoiceOptionProps = ChoiceOptionRadioProps | ChoiceOptionButtonProps

const containerClass: Record<ChoiceState, string> = {
  idle: 'border-border bg-white text-app-text hover:border-accent hover:bg-accent-soft',
  selected: 'border-accent bg-answered-soft text-primary',
  correct: 'border-correct-strong bg-correct-soft text-correct',
  wrong: 'border-wrong-strong bg-wrong-soft text-wrong',
  disabled: 'border-border bg-unanswered-soft text-text-light cursor-not-allowed',
}

const letterClass: Record<ChoiceState, string> = {
  idle: 'border-border bg-white text-primary',
  selected: 'border-accent bg-accent text-white',
  correct: 'border-correct-strong bg-correct-strong text-white',
  wrong: 'border-wrong-strong bg-wrong-strong text-white',
  disabled: 'border-border bg-white text-text-light',
}

const defaultStatusLabel: Partial<Record<ChoiceState, string>> = {
  correct: '正確答案',
  wrong: '你的答案（答錯）',
}

const base =
  'relative flex w-full min-h-[44px] items-start gap-3 rounded-lg border px-3 py-3 text-left text-reading transition-colors duration-150 sm:px-4'

function ChoiceBody({
  letter,
  state,
  children,
  after,
  statusLabel,
}: {
  letter: string
  state: ChoiceState
  children: ReactNode
  after?: ReactNode
  statusLabel?: string
}) {
  const label = statusLabel ?? defaultStatusLabel[state]
  const emphasize = state === 'selected' || state === 'correct' || state === 'wrong'
  return (
    <>
      <span
        className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-ui font-bold leading-none ${letterClass[state]}`}
      >
        {letter}
      </span>
      <span className={`min-w-0 flex-1 ${emphasize ? 'font-semibold' : ''}`}>
        <span>{children}</span>
        {after}
      </span>
      {(state === 'correct' || state === 'wrong') && (
        <span className="mt-0.5 shrink-0 font-bold">
          <span aria-hidden="true">{state === 'correct' ? '✓' : '✗'}</span>
          {label && <span className="sr-only">（{label}）</span>}
        </span>
      )}
    </>
  )
}

/**
 * Shared answer option for practice (button) and exam (radio).
 * Text is 16px (text-reading); min height 44px; state colours come from the
 * answered/correct/wrong tokens in index.css.
 */
export default function ChoiceOption(props: ChoiceOptionProps) {
  const { letter, children, after, statusLabel, describedBy, className = '' } = props

  if (props.kind === 'radio') {
    const state: ChoiceState =
      props.state ?? (props.disabled ? 'disabled' : props.checked ? 'selected' : 'idle')
    return (
      <label
        className={`${base} ${containerClass[state]} ${state === 'disabled' ? '' : 'cursor-pointer'} has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent has-[:focus-visible]:ring-offset-2 ${className}`}
      >
        <input
          type="radio"
          className="sr-only"
          name={props.name}
          value={props.value}
          checked={props.checked}
          disabled={props.disabled}
          onChange={() => props.onChange(props.value)}
          aria-describedby={describedBy}
        />
        <ChoiceBody letter={letter} state={state} after={after} statusLabel={statusLabel}>
          {children}
        </ChoiceBody>
      </label>
    )
  }

  const state: ChoiceState = props.state ?? (props.selected ? 'selected' : 'idle')
  return (
    <button
      type="button"
      className={`${base} ${containerClass[state]} ${props.locked ? 'cursor-default' : 'cursor-pointer'} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${className}`}
      onClick={() => {
        if (props.locked || state === 'disabled') return
        props.onSelect()
      }}
      aria-pressed={props.selected}
      aria-disabled={props.locked || state === 'disabled' || undefined}
      aria-describedby={describedBy}
    >
      <ChoiceBody letter={letter} state={state} after={after} statusLabel={statusLabel}>
        {children}
      </ChoiceBody>
    </button>
  )
}
