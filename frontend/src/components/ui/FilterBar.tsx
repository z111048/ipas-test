import type { ReactNode } from 'react'

interface FilterBarProps {
  title?: ReactNode
  result?: ReactNode
  children: ReactNode
  action?: ReactNode
  className?: string
}

export default function FilterBar({
  title = '篩選',
  result,
  children,
  action,
  className = '',
}: FilterBarProps) {
  return (
    <section className={`surface p-4 ${className}`}>
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        {title && <div className="section-title">{title}</div>}
        {result && <div className="text-[0.82rem] leading-6 text-text-light">{result}</div>}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {children}
      </div>
      {action && (
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          {action}
        </div>
      )}
    </section>
  )
}
