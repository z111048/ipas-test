import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loadGuideSearchIndex, searchGuides, type GuideSearchHit } from '../../data/guideSearch'
import type { GuideSearchIndexData } from '../../types'

const KIND_LABEL: Record<string, string> = { c: '章', s: '節', h: '標題' }

export default function GuideSearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState<GuideSearchIndexData | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const navigate = useNavigate()

  // 索引 204 KB，開啟時才載入
  useEffect(() => {
    if (!open || index) return
    setLoading(true)
    loadGuideSearchIndex()
      .then(setIndex)
      .finally(() => setLoading(false))
  }, [open, index])

  useEffect(() => {
    if (open) inputRef.current?.focus()
    else {
      setQuery('')
      setActiveIndex(0)
    }
  }, [open])

  const hits = useMemo(
    () => (index && query.trim() ? searchGuides(index, query) : []),
    [index, query],
  )

  useEffect(() => setActiveIndex(0), [query])

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, hits])

  if (!open) return null

  const go = (hit: GuideSearchHit) => {
    if (!hit.to) return
    navigate(hit.to)
    onClose()
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      onClose()
      return
    }
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
    <div
      className="fixed inset-0 z-200 flex items-start justify-center bg-slate-950/45 px-4 pt-[8vh]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="搜尋學習指引"
      >
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

        <div className="max-h-[60vh] overflow-y-auto">
          {loading && <p className="px-4 py-6 text-[0.85rem] text-text-light">載入索引中…</p>}
          {!loading && query.trim() && hits.length === 0 && (
            <p className="px-4 py-6 text-[0.85rem] text-text-light">找不到「{query}」</p>
          )}
          {!loading && !query.trim() && (
            <p className="px-4 py-6 text-[0.85rem] text-text-light">
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
                    className={`block w-full px-4 py-2 text-left transition-colors ${
                      isActive ? 'bg-[#f0f7ff]' : ''
                    } ${hit.to ? 'cursor-pointer' : 'cursor-default opacity-60'}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-border/60 px-1.5 py-0.5 text-[0.65rem] text-text-light">
                        {KIND_LABEL[hit.node.k]}
                      </span>
                      <span className="truncate text-[0.9rem] font-medium text-primary">{hit.node.t}</span>
                      {!hit.to && (
                        <span className="shrink-0 text-[0.65rem] text-text-light">（無對應段落）</span>
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
    </div>
  )
}
