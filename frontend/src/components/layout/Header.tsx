import { Link, useLocation } from 'react-router-dom'
import { SITE_NAME, SITE_TAGLINE, navLabelForPath } from '../../constants/navLabels'
import type { RefObject } from 'react'

interface HeaderProps {
  menuButtonRef?: RefObject<HTMLButtonElement | null>
  searchButtonRef?: RefObject<HTMLButtonElement | null>
  sidebarId: string
  sidebarOpen: boolean
  onMenuClick: () => void
  onSearchClick: () => void
}

export default function Header({
  menuButtonRef,
  searchButtonRef,
  sidebarId,
  sidebarOpen,
  onMenuClick,
  onSearchClick,
}: HeaderProps) {
  const location = useLocation()
  const section = navLabelForPath(location.pathname)

  return (
    <header className="app-header sticky top-0 z-100 min-h-14 border-b border-white/10 bg-primary text-white shadow-[0_8px_24px_rgba(15,23,42,0.18)]">
      <div className="flex h-full items-center justify-between gap-4 px-4 md:px-6">
        <button
          ref={menuButtonRef}
          type="button"
          className="touch-target md:hidden inline-flex h-11 w-11 items-center justify-center rounded-md border border-white/20 bg-white/8 text-white text-lg cursor-pointer"
          onClick={onMenuClick}
          aria-controls={sidebarId}
          aria-expanded={sidebarOpen}
          aria-label="選單"
        >
          ☰
        </button>
        <div className="min-w-0 flex-1">
          {/* 站名不是 <h1>：每頁唯一的 <h1> 由 PageHeader 提供。 */}
          <p className="m-0 min-w-0 text-[1rem] font-bold tracking-0">
            <Link to="/" className="block truncate leading-[2.75rem] text-white no-underline hover:text-white/90 sm:leading-snug">
              {SITE_NAME}
            </Link>
          </p>
          <div className="hidden text-caption text-on-dark-muted sm:flex sm:items-center sm:gap-1.5">
            <span>{SITE_TAGLINE}</span>
            {section && (
              <>
                <span aria-hidden="true" className="text-on-dark-muted">·</span>
                <span className="font-semibold text-white/90">{section}</span>
              </>
            )}
          </div>
        </div>
        <button
          ref={searchButtonRef}
          type="button"
          onClick={onSearchClick}
          className="touch-target inline-flex shrink-0 items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-meta text-white/90 hover:bg-white/16"
          aria-label="搜尋學習指引"
        >
          <span aria-hidden="true">🔍</span>
          <span className="hidden sm:inline">搜尋</span>
          <kbd className="hidden rounded border border-white/25 px-1 text-caption text-on-dark-muted md:inline">Ctrl K</kbd>
        </button>
      </div>
    </header>
  )
}
