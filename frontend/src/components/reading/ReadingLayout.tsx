import type { ReactNode } from 'react'

export function ReadingContent({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`mx-auto w-full max-w-[76ch] min-w-0 overflow-x-hidden [overflow-wrap:anywhere] ${className}`}>
      {children}
    </div>
  )
}

export function ReadingSurface({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`surface overflow-hidden p-4 sm:p-6 ${className}`}>
      {children}
    </section>
  )
}

export function ReadingAuxiliary({
  title,
  children,
  className = '',
}: {
  title: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <details className={`surface overflow-hidden p-4 sm:p-5 ${className}`}>
      <summary className="min-h-11 cursor-pointer text-primary font-semibold">
        {title}
      </summary>
      <div className="mt-4 min-w-0 overflow-x-auto">
        {children}
      </div>
    </details>
  )
}
