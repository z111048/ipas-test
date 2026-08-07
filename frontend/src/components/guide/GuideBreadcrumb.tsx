import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import type { BreadcrumbCrumb } from '../../data/guideNav'

/**
 * 學習指引的位置路徑：級別 › 科目 › 章 › 節。
 * 最後一項是目前頁面，不做成連結。
 */
export default function GuideBreadcrumb({ crumbs }: { crumbs: BreadcrumbCrumb[] }) {
  if (crumbs.length === 0) return null

  return (
    <nav aria-label="麵包屑" className="mb-1.5 text-[0.75rem] leading-5 text-text-light">
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1
          return (
            <Fragment key={`${crumb.label}-${index}`}>
              <li className="min-w-0">
                {crumb.to && !isLast ? (
                  <Link to={crumb.to} className="no-underline hover:text-accent">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className={isLast ? 'text-primary font-medium' : undefined}>
                    {crumb.label}
                  </span>
                )}
              </li>
              {!isLast && <li aria-hidden="true" className="text-text-light/50">›</li>}
            </Fragment>
          )
        })}
      </ol>
    </nav>
  )
}
