import type { ReactNode } from 'react'

export type BadgeTone = 'neutral' | 'accent' | 'answered' | 'correct' | 'wrong' | 'warning'

export interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  /** Optional leading icon/glyph (decorative). */
  icon?: ReactNode
  title?: string
  /** Allow long text (e.g. citation titles) to wrap instead of overflowing. */
  wrap?: boolean
  className?: string
}

const toneClass: Record<BadgeTone, string> = {
  neutral: '',
  accent: 'badge-accent',
  answered: 'badge-answered',
  correct: 'badge-correct',
  wrong: 'badge-wrong',
  warning: 'badge-warning',
}

/** Non-interactive status label (`.badge`), 12px minimum. */
export default function Badge({
  tone = 'neutral',
  children,
  icon,
  title,
  wrap = false,
  className = '',
}: BadgeProps) {
  return (
    <span className={`badge ${toneClass[tone]} ${wrap ? 'badge-wrap' : ''} ${className}`} title={title}>
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
    </span>
  )
}
