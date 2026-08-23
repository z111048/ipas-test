import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dialog } from '../ui'
import { loadGuideSearchIndex, searchGuides, type GuideSearchHit } from '../../data/guideSearch'
import type { GuideSearchIndexData } from '../../types'

const KIND_LABEL: Record<string, string> = { c: '章', s: '節', h: '標題' }

interface GuideSearchDialogProps {
  open: boolean
  onClose: () => void
  restoreFocusRef?: RefObject<HTMLElement | null>
}

export default function GuideSearchDialog({ open, onClose, restoreFocusRef }: GuideSearchDialogProps) {
  const [index, setIndex] = useState<GuideSearchIndexData | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const descriptionId = 'guide-search-description'
  const navigate = useNavigate()

  // 索引 204 KB，開啟時才載入
  useEffect(() => {
    if (!open || index) return
    setLoading(true)
    loadGuideSearchIndex()
      .then(setIndex)
      .finally(() => setLoading(false))
  }, [open, index])

  const hits = useMemo(
    () => (index && query.trim() ? searchGuides(index, query) : []),
    [index, query],
  )

  useEffect(() => setActiveIndex(0), [query])

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, hits])

  const go = (hit: GuideSearchHit) => {
    if (!hit.to) return
    navigate(hit.to)
    onClose()
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => Math.min(current + 1, hits.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => Math.max(current - 1, 0))
    } else if (event.key === 'Enter' && hits[activeIndex]) {
      event.preventDefault()
      go(hits[activeIndex])
    }
  }

  return (
    <Dialog
      open={open}
      title="搜尋學習指引"
      descriptionId={descriptionId}
      onClose={onClose}
      initialFocusRef={inputRef}
      restoreFocusRef={restoreFocusRef}
      mobilePosition="top"
      className="max-h-[calc(100dvh-1rem)] rounded-2xl border border-border bg-white shadow-2xl sm:max-w-2xl"
    >
      <div>
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span aria-hidden="true" className="text-text-light">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="搜尋章節與標題，例如「梯度下降」"
            className="w-full border-none text-[0.95rem] text-app-text outline-none placeholder:text-text-light/70"
            aria-label="搜尋關鍵字"
          />
          <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-[0.68rem] text-text-light sm:inline">Esc</kbd>
        </div>

        <div className="max-h-[calc(100dvh-5.5rem)] overflow-y-auto overscroll-contain">
          {loading && <p className="px-4 py-6 text-[0.85rem] text-text-light">載入索引中…</p>}
          {!loading && query.trim() && hits.length === 0 && (
            <p className="px-4 py-6 text-[0.85rem] text-text-light">找不到「{query}」</p>
          )}
          {!loading && !query.trim() && (
            <p id={descriptionId} className="px-4 py-6 text-[0.85rem] text-text-light">
              可搜尋全部 5 份學習指引的章、節與內文標題。↑↓ 選擇，Enter 前往。
            </p>
          )}
          <ul ref={listRef} className="py-1">
            {hits.map((hit, position) => {
              const isActive = position === activeIndex
              const label = `${hit.level}・${hit.subject ?? hit.subjectId}`
              return (
                <li key={`${hit.subjectId}-${hit.node.id}`}>
                  <button
                    type="button"
                    data-active={isActive}
                    disabled={!hit.to}
                    onMouseEnter={() => setActiveIndex(position)}
                    onClick={() => go(hit)}
                    className={`block min-h-[44px] w-full px-4 py-2 text-left transition-colors ${
                      isActive ? 'bg-[#f0f7ff]' : ''
                    } ${hit.to ? 'cursor-pointer' : 'cursor-default opacity-60'}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-border/60 px-1.5 py-0.5 text-[0.65rem] text-text-light">
                        {KIND_LABEL[hit.node.k]}
                      </span>
                      <span className="truncate text-[0.9rem] font-medium text-primary">{hit.node.t}</span>
                      {hit.approximate && (
                        <span className="shrink-0 text-[0.65rem] text-text-light">概略位置</span>
                      )}
                    </div>
                    <div className="mt-0.5 truncate text-[0.72rem] text-text-light">
                      {[label, ...hit.path].join(' › ')}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </Dialog>
  )
}
