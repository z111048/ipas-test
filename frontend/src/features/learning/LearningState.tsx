import type { ReactNode } from 'react'
import { PageHeader, StatePanel } from '../../components/ui'

interface LearningStateProps {
  tone: 'loading' | 'empty' | 'error'
  /** Rendered as the page's only <h1>. */
  title: ReactNode
  children?: ReactNode
  action?: ReactNode
}

/**
 * Full-page loading / empty / error state for the learning routes.
 * Keeps the one-<h1>-per-page rule while the page content is unavailable.
 */
export default function LearningState({ tone, title, children, action }: LearningStateProps) {
  return (
    <div className="page-shell w-full" aria-busy={tone === 'loading' || undefined}>
      <PageHeader variant="plain" title={title} actions={action} className="mb-5" />
      {children && <StatePanel tone={tone}>{children}</StatePanel>}
    </div>
  )
}
