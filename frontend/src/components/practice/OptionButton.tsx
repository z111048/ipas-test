interface OptionButtonProps {
  optKey: 'A' | 'B' | 'C' | 'D'
  value: string
  state: 'idle' | 'correct' | 'wrong'
  locked: boolean
  selected: boolean
  onClick: () => void
  describedBy?: string
}

export default function OptionButton({
  optKey,
  value,
  state,
  locked,
  selected,
  onClick,
  describedBy,
}: OptionButtonProps) {
  const base =
    'w-full min-h-[44px] flex items-start gap-2 text-left px-4 py-3 rounded-lg border text-[0.9rem] leading-relaxed transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2'
  const stateClass =
    state === 'correct'
      ? 'bg-[#ecfdf3] border-success text-success font-semibold'
      : state === 'wrong'
        ? 'bg-[#fdf2f2] border-error text-error'
        : selected
          ? 'bg-[#eff6ff] border-accent text-primary font-semibold'
          : 'bg-white border-border hover:bg-[#f8fbff] hover:border-accent text-app-text'

  return (
    <button
      type="button"
      className={`${base} ${stateClass} ${locked ? 'cursor-default' : ''}`}
      onClick={() => {
        if (locked) return
        onClick()
      }}
      aria-pressed={selected}
      aria-disabled={locked}
      aria-describedby={describedBy}
    >
      <span className="min-w-0 flex-1">
        <strong>({optKey})</strong> {value}
      </span>
      {state === 'correct' && (
        <span aria-hidden="true" className="shrink-0 font-bold text-success">✓</span>
      )}
      {state === 'wrong' && (
        <span aria-hidden="true" className="shrink-0 font-bold text-error">✗</span>
      )}
    </button>
  )
}
