import type { ReactNode } from 'react'

type StateTone = 'loading' | 'empty' | 'error' | 'status'

interface StatePanelProps {
  tone?: StateTone
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}

const toneClass: Record<StateTone, string> = {
  loading: 'border-border bg-white text-text-light',
  empty: 'border-border bg-white text-text-light',
  error: 'border-red-200 bg-red-50 text-red-700',
  status: 'border-[#d7e7f5] bg-[#f4f9fd] text-app-text',
}

export default function StatePanel({
  tone = 'status',
  title,
  children,
  action,
  className = '',
}: StatePanelProps) {
  return (
    <section
      className={`rounded-lg border p-4 text-[0.9rem] leading-7 ${toneClass[tone]} ${className}`}
      aria-live={tone === 'loading' || tone === 'error' ? 'polite' : undefined}
    >
      {title && <div className="mb-1 font-semibold text-primary">{title}</div>}
      {children && <div>{children}</div>}
      {action && <div className="mt-3 flex flex-wrap gap-2">{action}</div>}
    </section>
  )
}
