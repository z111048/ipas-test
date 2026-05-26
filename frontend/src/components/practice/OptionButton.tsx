interface OptionButtonProps {
  optKey: 'A' | 'B' | 'C' | 'D'
  value: string
  state: 'idle' | 'correct' | 'wrong'
  disabled: boolean
  onClick: () => void
}

export default function OptionButton({ optKey, value, state, disabled, onClick }: OptionButtonProps) {
  const base = 'w-full text-left px-4 py-3 rounded-lg border text-[0.9rem] leading-relaxed transition-all duration-150 cursor-pointer'
  const stateClass =
    state === 'correct'
      ? 'bg-[#ecfdf3] border-success text-success font-semibold'
      : state === 'wrong'
        ? 'bg-[#fdf2f2] border-error text-error'
        : 'bg-white border-border hover:bg-[#f8fbff] hover:border-accent text-app-text'

  return (
    <button
      className={`${base} ${stateClass} ${disabled ? 'cursor-default' : ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      <strong>({optKey})</strong> {value}
    </button>
  )
}
