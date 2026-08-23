import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

interface SegmentOption {
  value: string
  label: ReactNode
  to?: string
  disabled?: boolean
  title?: string
}

interface SegmentedControlProps {
  label: string
  options: SegmentOption[]
  value: string
  onChange?: (value: string) => void
  className?: string
}

function segmentClass(active: boolean, disabled?: boolean) {
  if (disabled) {
    return 'min-h-11 rounded-lg border border-border bg-[#f8fafc] px-3 py-2 text-[0.85rem] text-text-light opacity-70'
  }
  return `min-h-11 rounded-lg border px-3 py-2 text-[0.85rem] font-semibold no-underline transition-colors ${
    active
      ? 'border-accent bg-accent text-white'
      : 'border-border bg-white text-primary hover:border-accent hover:text-accent'
  }`
}

export default function SegmentedControl({
  label,
  options,
  value,
  onChange,
  className = '',
}: SegmentedControlProps) {
  return (
    <div className={className}>
      <div className="mb-1.5 text-[0.78rem] font-semibold text-text-light">{label}</div>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap" role="group" aria-label={label}>
        {options.map((option) => {
          const active = option.value === value
          if (option.to && !option.disabled) {
            return (
              <Link
                key={option.value}
                to={option.to}
                className={segmentClass(active)}
                aria-current={active ? 'true' : undefined}
                title={option.title}
              >
                {option.label}
              </Link>
            )
          }
          return (
            <button
              key={option.value}
              type="button"
              disabled={option.disabled}
              onClick={() => onChange?.(option.value)}
              className={segmentClass(active, option.disabled)}
              aria-pressed={active}
              title={option.title}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
