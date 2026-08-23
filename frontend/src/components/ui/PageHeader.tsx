import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
  className?: string
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
  className = '',
}: PageHeaderProps) {
  return (
    <header className={`page-header ${className}`}>
      {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-primary mb-1">{title}</h1>
          {description && (
            <div className="max-w-4xl text-[0.9rem] leading-7 text-text-light">
              {description}
            </div>
          )}
        </div>
        {(meta || actions) && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {meta}
            {actions}
          </div>
        )}
      </div>
    </header>
  )
}
