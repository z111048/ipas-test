import { Link, useLocation } from 'react-router-dom'
import { SEARCH_LABEL, SITE_NAME, SITE_TAGLINE, navLabelForPath } from '../../constants/navLabels'
import type { RefObject } from 'react'
import SearchIcon from './SearchIcon'

interface HeaderProps {
  menuButtonRef?: RefObject<HTMLButtonElement | null>
  searchButtonRef?: RefObject<HTMLButtonElement | null>
  sidebarId: string
  sidebarOpen: boolean
  onMenuClick: () => void
  onSearchClick: () => void
  /** Focus mode (exam): hide the whole header below 768px. */
  hiddenOnMobile?: boolean
}

const isApplePlatform = typeof navigator !== 'undefined'
  && /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent)

export default function Header({
  menuButtonRef,
  searchButtonRef,
  sidebarId,
  sidebarOpen,
  onMenuClick,
  onSearchClick,
  hiddenOnMobile = false,
}: HeaderProps) {
  const location = useLocation()
  const section = navLabelForPath(location.pathname)

  return (
    <header
      className={`app-header sticky top-0 z-100 min-h-14 border-b border-white/10 bg-primary text-white shadow-[0_8px_24px_rgba(15,23,42,0.18)] ${
        hiddenOnMobile ? 'max-md:hidden' : ''
      }`}
    >
      <div className="flex h-full items-center justify-between gap-3 px-4 md:gap-4 md:px-6">
        <button
          ref={menuButtonRef}
          type="button"
          className="touch-target md:hidden inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-white/20 bg-white/8 text-white text-lg cursor-pointer"
          onClick={onMenuClick}
          aria-controls={sidebarId}
          aria-expanded={sidebarOpen}
          aria-label="選單"
        >
          <span aria-hidden="true">☰</span>
        </button>
        <div className="min-w-0 flex-1">
          {/* 站名不是 <h1>：每頁唯一的 <h1> 由 PageHeader 提供。 */}
          <p className="m-0 min-w-0 text-[1rem] font-bold tracking-0">
            <Link
              to="/"
              className="flex min-h-11 min-w-0 flex-col justify-center text-white no-underline hover:text-white/90 sm:block sm:min-h-0"
            >
              <span className="block truncate leading-tight sm:leading-snug">{SITE_NAME}</span>
              {/* 手機版的所在位置（桌機版在下一行 tagline 後面） */}
              {section && (
                <span
                  className="block truncate text-caption font-semibold leading-4 text-on-dark-muted sm:hidden"
                  aria-hidden="true"
                >
                  {section}
                </span>
              )}
            </Link>
          </p>
          <div className="hidden text-caption text-on-dark-muted sm:flex sm:min-w-0 sm:items-center sm:gap-1.5">
            <span className="truncate">{SITE_TAGLINE}</span>
            {section && (
              <>
                <span aria-hidden="true" className="text-on-dark-muted">·</span>
                <span className="shrink-0 font-semibold text-white/90">{section}</span>
              </>
            )}
          </div>
        </div>
        <button
          ref={searchButtonRef}
          type="button"
          onClick={onSearchClick}
          className="touch-target inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-meta text-white/90 hover:bg-white/16"
          aria-label={SEARCH_LABEL}
          aria-keyshortcuts={isApplePlatform ? 'Meta+K' : 'Control+K'}
        >
          <SearchIcon />
          <span className="hidden md:inline">{SEARCH_LABEL}</span>
          <kbd className="hidden rounded border border-white/25 px-1 font-sans text-caption text-on-dark-muted lg:inline">
            {isApplePlatform ? '⌘ K' : 'Ctrl K'}
          </kbd>
        </button>
      </div>
    </header>
  )
}
