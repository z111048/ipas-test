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
  error: 'border-wrong-line bg-wrong-soft text-wrong',
  status: 'border-transparent bg-accent-soft text-app-text',
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
      className={`rounded-lg border p-4 text-body ${toneClass[tone]} ${className}`}
      aria-live={tone === 'loading' || tone === 'error' ? 'polite' : undefined}
    >
      {title && <div className={`mb-1 font-semibold ${tone === 'error' ? 'text-wrong' : 'text-primary'}`}>{title}</div>}
      {children && <div>{children}</div>}
      {action && <div className="mt-3 flex flex-wrap gap-2">{action}</div>}
    </section>
  )
}
