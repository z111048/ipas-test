import type { ReactNode, Ref } from 'react'

/**
 * 學習指引與主題式文章共用的閱讀版面。
 *
 * - ReadingContent：正文欄。最寬約 38em（中文每行約 35–40 字）、16px（text-reading）、
 *   行高 1.8；手機靠左對齊（.content-justify 只在 md 以上左右對齊）。
 *   表格／公式／圖片各自在自己的容器內水平捲動，整欄 overflow-x-hidden，頁面永遠不橫向溢出。
 * - ReadingLayout：正文＋右側「本頁目錄」。目錄欄從 lg（1024px）起出現並保持可見；
 *   lg 以下由頁面自行提供抽屜或摺疊目錄。
 * - ReadingToc：目錄清單。縮排依「相對最淺層級」計算，標題去掉結尾冒號。
 */

/** Body-text classes for a reading paragraph (shared by guide and article blocks). */
export const READING_PARAGRAPH_CLASS = 'text-reading leading-[1.8] text-app-text mb-4 content-justify'
/** Body-text classes for a list item line. */
export const READING_LIST_ITEM_CLASS = 'text-reading leading-[1.8] text-app-text mb-2 content-justify'
/** Wrapper for a wide element (table / formula / image) that scrolls inside its own box. */
export const READING_WIDE_BOX_CLASS = 'max-w-full overflow-x-auto overscroll-x-contain'

export function ReadingContent({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`mx-auto w-full max-w-[38em] min-w-0 overflow-x-hidden text-reading leading-[1.8] [overflow-wrap:anywhere] [&_img]:max-w-full ${className}`}
    >
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
    // 輕量摺疊列：不包卡片，只是一行可點的文字＋下方細分隔線。
    <details className={`group border-b border-border ${className}`}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 py-2 text-ui font-semibold text-primary-light hover:text-accent [&::-webkit-details-marker]:hidden">
        <span aria-hidden="true" className="inline-block text-caption text-text-light transition-transform group-open:rotate-90">▶</span>
        {title}
      </summary>
      <div className="pb-4 min-w-0 overflow-x-auto">
        {children}
      </div>
    </details>
  )
}

export interface ReadingLayoutProps {
  /** Main reading column. */
  children: ReactNode
  /** Right-side table of contents (visible from lg up). */
  toc?: ReactNode
  className?: string
  /** Extra classes on the main column (e.g. to make it its own scroll container). */
  mainClassName?: string
  mainRef?: Ref<HTMLDivElement>
  /**
   * Extra classes on the aside. Default is sticky inside the page scroller;
   * pass e.g. 'h-full' when the main column scrolls by itself.
   */
  asideClassName?: string
}

export function ReadingLayout({
  children,
  toc,
  className = '',
  mainClassName = '',
  mainRef,
  asideClassName = 'lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100dvh-var(--app-header-h,0px)-2rem)]',
}: ReadingLayoutProps) {
  return (
    <div
      className={`grid grid-cols-1 gap-4 ${toc ? 'lg:grid-cols-[minmax(0,1fr)_15rem] xl:grid-cols-[minmax(0,1fr)_17rem]' : ''} ${className}`}
    >
      <div ref={mainRef} className={`min-w-0 ${mainClassName}`}>
        {children}
      </div>
      {toc && (
        <aside className={`hidden min-h-0 lg:flex lg:flex-col ${asideClassName}`}>
          <div className="flex min-h-0 flex-1 flex-col border-l border-border py-1 pl-4">
            <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1 scrollbar-hidden">
              {toc}
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}

export interface ReadingTocEntry {
  /** Target id to scroll to; empty string = non-clickable grouping label. */
  id: string
  title: string
  /** Heading level / depth; indentation is relative to the shallowest entry. */
  level: number
  anchor?: string
}

/** 「1. 前言：」→「1. 前言」 */
export function tocLabel(title: string) {
  return title.replace(/[\s　]*[：:]+[\s　]*$/, '').trim()
}

export function ReadingToc({
  title = '本頁目錄',
  entries,
  activeId,
  onSelect,
  compact = false,
  maxIndentLevels = 3,
}: {
  title?: string
  entries: ReadingTocEntry[]
  activeId?: string | null
  onSelect: (entry: ReadingTocEntry) => void
  /** Mobile drawer: 44px rows and text-ui. */
  compact?: boolean
  maxIndentLevels?: number
}) {
  if (entries.length === 0) return null
  const minLevel = Math.min(...entries.map((entry) => entry.level))
  const rowClass = compact
    ? 'min-h-11 py-2.5 text-ui'
    : 'min-h-11 py-2.5 text-ui md:min-h-0 md:py-1.5'

  return (
    <nav aria-label={title}>
      <div className="section-title mb-3">{title}</div>
      <ul className="space-y-0.5">
        {entries.map((entry, index) => {
          const depth = Math.min(Math.max(entry.level - minLevel, 0), maxIndentLevels)
          const style = { paddingLeft: `${0.5 + depth * 0.85}rem` }
          const label = tocLabel(entry.title)
          const top = depth === 0
          const key = `${entry.id || entry.anchor || index}-${entry.title}`
          if (!entry.id) {
            return (
              <li
                key={key}
                className={`block border-l-2 border-l-transparent pr-2 leading-5 text-text-light ${rowClass}`}
                style={style}
              >
                {label}
              </li>
            )
          }
          const active = activeId === entry.id
          return (
            <li key={key}>
              <button
                type="button"
                onClick={() => onSelect(entry)}
                aria-current={active ? 'true' : undefined}
                className={`block w-full rounded-md border-l-2 pr-2 text-left leading-5 transition-colors ${rowClass} ${
                  active
                    ? 'border-l-accent bg-accent-soft font-semibold text-accent'
                    : `border-l-transparent hover:bg-accent-soft hover:text-accent ${top ? 'font-medium text-primary' : 'text-text-light'}`
                }`}
                style={style}
              >
                {label}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
