import type { ReactNode, Ref } from 'react'

export type PageHeaderVariant = 'default' | 'plain' | 'hero'

export interface PageHeaderProps {
  /** Optional short Chinese context line above the title (e.g. 「學習指引」). Omit when it repeats the title. */
  eyebrow?: ReactNode
  /** The page's single <h1>. Every routed page renders exactly one PageHeader. */
  title: ReactNode
  description?: ReactNode
  /** One meta row under the description: pills / badges / counts. */
  meta?: ReactNode
  /** Primary actions, right-aligned on desktop, stacked under the text on mobile. */
  actions?: ReactNode
  /**
   * default: white card (most pages).
   * plain:   no card chrome, neutral (404, empty states that are pages).
   * hero:    dark home hero panel; `eyebrow` may be a row of `.hero-chip`, `aside` holds stats.
   */
  variant?: PageHeaderVariant
  /** Extra column (hero only, e.g. stats); rendered beside the title on lg screens. */
  aside?: ReactNode
  /** Classes for the aside wrapper (hero only), e.g. 'hidden sm:block' to drop it on phones. */
  asideClassName?: string
  /** id for the <h1>, e.g. to label a region via aria-labelledby. */
  titleId?: string
  /** Ref to the <h1>, e.g. to move focus to it after a state change. */
  titleRef?: Ref<HTMLHeadingElement>
  /** Pass -1 together with titleRef to make the <h1> a programmatic focus target. */
  titleTabIndex?: number
  className?: string
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
  variant = 'default',
  aside,
  asideClassName = '',
  titleId,
  titleRef,
  titleTabIndex,
  className = '',
}: PageHeaderProps) {
  const isHero = variant === 'hero'
  const shellClass = isHero
    ? 'hero-panel page-header-hero px-4 py-5 sm:px-6 md:px-8 md:py-7'
    : variant === 'plain'
      ? 'page-header page-header-plain'
      : 'page-header'

  const body = (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <div className={isHero ? 'mb-3 flex flex-wrap gap-2' : 'eyebrow mb-2'}>{eyebrow}</div>
        )}
        <h1
          id={titleId}
          ref={titleRef}
          tabIndex={titleTabIndex}
          className={`page-header-title mb-1 ${titleTabIndex !== undefined ? 'focus:outline-none' : ''}`}
        >
          {title}
        </h1>
        {description && <div className="page-header-description mt-1">{description}</div>}
        {meta && <div className="page-header-meta mt-3">{meta}</div>}
        {isHero && actions && (
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">{actions}</div>
        )}
      </div>
      {!isHero && actions && (
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          {actions}
        </div>
      )}
    </div>
  )

  if (isHero) {
    return (
      <header className={`${shellClass} ${className}`}>
        <div className="hero-grid" aria-hidden="true" />
        <div
          className={`relative grid gap-5 ${aside ? 'lg:grid-cols-[minmax(0,1fr)_minmax(260px,340px)] lg:items-end' : ''}`}
        >
          {body}
          {aside && <div className={`min-w-0 ${asideClassName}`}>{aside}</div>}
        </div>
      </header>
    )
  }

  return <header className={`${shellClass} ${className}`}>{body}</header>
}
