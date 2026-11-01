import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export interface ChipProps {
  children: ReactNode
  /** Selected/current state. Button chips expose aria-pressed, link chips aria-current. */
  active?: boolean
  /** Render as a router link (filter state in the URL). */
  to?: string
  onClick?: () => void
  disabled?: boolean
  /** Small trailing count, e.g. number of questions. */
  count?: ReactNode
  title?: string
  /** aria-current value for link chips (default 'true'; use 'page' for navigation). */
  current?: 'page' | 'true'
  /** Colour tone; 'wrong' = red chip for lists of incorrectly answered questions. */
  tone?: 'default' | 'wrong'
  className?: string
}

/**
 * Filter / toggle chip (`.chip`). Height is 44px on touch / narrow viewports.
 * Put several in a `.chip-row` (wraps on desktop, scrolls sideways on mobile),
 * or use <ChipGroup>.
 */
export default function Chip({
  children,
  active = false,
  to,
  onClick,
  disabled = false,
  count,
  title,
  current = 'true',
  tone = 'default',
  className = '',
}: ChipProps) {
  const cls = `chip ${tone === 'wrong' ? 'chip-wrong' : ''} ${className}`
  const content = (
    <>
      <span>{children}</span>
      {count !== undefined && count !== null && <span className="chip-count">{count}</span>}
    </>
  )
  if (to && !disabled) {
    return (
      <Link
        to={to}
        className={cls}
        aria-current={active ? current : undefined}
        title={title}
        onClick={onClick}
      >
        {content}
      </Link>
    )
  }
  return (
    <button
      type="button"
      className={cls}
      aria-pressed={active}
      disabled={disabled}
      title={title}
      onClick={onClick}
    >
      {content}
    </button>
  )
}

export interface ChipGroupProps {
  /** Accessible name for the group; shown above the row unless `labelHidden`. */
  label: string
  labelHidden?: boolean
  children: ReactNode
  className?: string
}

/** Labelled `.chip-row` wrapper (role=group). */
export function ChipGroup({ label, labelHidden = false, children, className = '' }: ChipGroupProps) {
  return (
    <div className={className}>
      {!labelHidden && <div className="field-label">{label}</div>}
      <div className="chip-row" role="group" aria-label={label}>
        {children}
      </div>
    </div>
  )
}
