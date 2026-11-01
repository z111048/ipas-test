import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import pdfGallery from '../generated/pdfGallery.json'
import type { PdfImageAsset, PdfImageGallery } from '../types'
import { publicAsset } from '../utils/assets'
import { catalogExams, catalogLevels } from '../data/resourceCatalog'
import { Chip, ChipGroup, Dialog, FilterBar, PageHeader, StatePanel } from '../components/ui'
import { NAV_LABELS } from '../constants/navLabels'

const PAGE_SIZE = 24

const keyLabels: Record<string, string> = {
  guide1: '科目一學習指引',
  guide2: '科目二學習指引',
  guide3: '科目三學習指引',
  errata: '學習指引勘誤表',
  briefing: '能力鑑定簡章',
  exam1: '科目一公告試題',
  exam2: '科目二公告試題',
  exam3: '科目三公告試題',
  sample: '考試樣題',
}

// 公告試題的圖片 key 就是卷別 key（如 mid_1141_s1），名稱從 resource catalog 取
function keyLabel(key: string) {
  return keyLabels[key] ?? catalogExams.find((exam) => exam.key === key)?.label ?? '教材'
}

const keyOrder = ['guide1', 'guide2', 'guide3', 'errata', 'briefing', 'sample', 'exam1', 'exam2', 'exam3']

function keyRank(key: string) {
  const index = keyOrder.indexOf(key)
  return index === -1 ? keyOrder.length : index
}

function compareAssets(a: PdfImageAsset, b: PdfImageAsset) {
  const levelDiff = (a.level ?? '').localeCompare(b.level ?? '', 'zh-Hant')
  if (levelDiff !== 0) return levelDiff
  const keyDiff = keyRank(a.key) - keyRank(b.key)
  if (keyDiff !== 0) return keyDiff
  const typeOrder = { page: 0, image: 1, table: 2 }
  if (a.type !== b.type) return typeOrder[a.type] - typeOrder[b.type]
  if (a.page_number !== b.page_number) return a.page_number - b.page_number
  return a.asset_id.localeCompare(b.asset_id)
}

const typeLabel = (type: PdfImageAsset['type']) => (type === 'page' ? '頁面' : type === 'table' ? '表格' : '圖片')

function pageText(item: PdfImageAsset) {
  return `第 ${item.page_number} 頁${item.page_label ? `（教材頁碼 ${item.page_label}）` : ''}`
}

function assetAlt(item: PdfImageAsset) {
  return `${keyLabel(item.key)} ${pageText(item)} ${typeLabel(item.type)}`
}

function AssetPreview({ item }: { item: PdfImageAsset }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="h-full w-full flex items-center justify-center px-4 text-center text-ui text-wrong bg-wrong-soft">
        圖片載入失敗
      </div>
    )
  }

  return (
    <img
      src={publicAsset(item.path)}
      alt={assetAlt(item)}
      loading="lazy"
      onError={() => setFailed(true)}
      className="max-w-full max-h-full object-contain"
    />
  )
}

export default function ImageGalleryPage() {
  const gallery = pdfGallery as PdfImageGallery
  const [searchParams] = useSearchParams()
  const queryString = searchParams.toString()
  const [selectedLevel, setSelectedLevel] = useState(searchParams.get('level') ?? 'all')
  const [selectedKey, setSelectedKey] = useState(searchParams.get('key') ?? 'all')
  const [selectedType, setSelectedType] = useState('all')
  const [pageQuery, setPageQuery] = useState('')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [active, setActive] = useState<PdfImageAsset | null>(null)
  const lightboxTriggerRef = useRef<HTMLButtonElement | null>(null)
  const lightboxCloseRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    setSelectedLevel(searchParams.get('level') ?? 'all')
    setSelectedKey(searchParams.get('key') ?? 'all')
    setSelectedType(searchParams.get('type') ?? 'all')
    setPageQuery(searchParams.get('page') ?? '')
    setActive(null)
  }, [queryString])

  const levels = useMemo(() => {
    const unique = Array.from(new Set(gallery.items.map((item) => item.level).filter(Boolean))) as string[]
    // 初級、中級依 catalog 順序在前，共用等其他來源排最後
    const rank = (level: string) => {
      const index = catalogLevels.findIndex((row) => row.dataLevel === level)
      return index === -1 ? catalogLevels.length : index
    }
    return unique.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, 'zh-Hant'))
  }, [gallery])

  const keys = useMemo(() => {
    const unique = Array.from(new Set(
      gallery.items
        .filter((item) => selectedLevel === 'all' || item.level === selectedLevel)
        .map((item) => item.key)
    ))
    return unique.sort((a, b) => keyRank(a) - keyRank(b))
  }, [gallery, selectedLevel])

  const filtered = useMemo(() => {
    const page = pageQuery.trim()
    return gallery.items.filter((item) => {
      if (selectedKey !== 'all' && item.key !== selectedKey) return false
      if (selectedLevel !== 'all' && item.level !== selectedLevel) return false
      if (selectedType !== 'all' && item.type !== selectedType) return false
      if (page && item.page_number !== Number(page) && item.page_label !== page) return false
      return true
    }).sort(compareAssets)
  }, [gallery, pageQuery, selectedKey, selectedLevel, selectedType])

  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [pageQuery, selectedKey, selectedLevel, selectedType])

  const visibleItems = filtered.slice(0, visibleCount)

  const counts = useMemo(() => {
    const items = gallery.items
    return {
      total: items.length,
      page: items.filter((item) => item.type === 'page').length,
      image: items.filter((item) => item.type === 'image').length,
      table: items.filter((item) => item.type === 'table').length,
    }
  }, [gallery])

  const filteredCounts = useMemo(() => {
    const items = gallery.items.filter((item) =>
      (selectedLevel === 'all' || item.level === selectedLevel) &&
      (selectedKey === 'all' || item.key === selectedKey)
    )
    return {
      page: items.filter((item) => item.type === 'page').length,
      image: items.filter((item) => item.type === 'image').length,
      table: items.filter((item) => item.type === 'table').length,
    }
  }, [gallery, selectedKey, selectedLevel])

  const activeIndex = active ? filtered.findIndex((item) => item.id === active.id) : -1
  const goRelative = (delta: number) => {
    if (activeIndex === -1) return
    const next = filtered[activeIndex + delta]
    if (next) setActive(next)
  }

  // Keyboard: Esc closes the lightbox, ←/→ step through the filtered results.
  useEffect(() => {
    if (!active) return
    const onKey = (event: KeyboardEvent) => {
      const target = event.target
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      ) {
        return
      }
      if (event.key === 'Escape') setActive(null)
      else if (event.key === 'ArrowLeft') goRelative(-1)
      else if (event.key === 'ArrowRight') goRelative(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, activeIndex, filtered])

  return (
    <div className="page-shell">
      <PageHeader
        className="mb-5"
        title={NAV_LABELS.images.label}
        description="依頁碼瀏覽教材中的圖片、表格與頁面。"
        meta={<span className="pill">{counts.total} 項</span>}
      />

      <FilterBar
        className="mb-5"
        title="篩選圖片與表格"
        result={`顯示 ${visibleItems.length} / ${filtered.length} 項`}
        action={(selectedLevel !== 'all' || selectedKey !== 'all' || selectedType !== 'all' || pageQuery) && (
          <button
            type="button"
            onClick={() => {
              setSelectedKey('all')
              setSelectedLevel('all')
              setSelectedType('all')
              setPageQuery('')
            }}
            className="btn-outline"
          >
            清除篩選
          </button>
        )}
      >
        <ChipGroup label="級別">
          {['all', ...levels].map((level) => (
            <Chip
              key={level}
              active={selectedLevel === level}
              onClick={() => {
                setSelectedLevel(level)
                setSelectedKey('all')
              }}
            >
              {level === 'all' ? '全部級別' : level}
            </Chip>
          ))}
        </ChipGroup>
        <label className="field-label">
          教材
          <select
            value={selectedKey}
            onChange={(event) => setSelectedKey(event.target.value)}
            className="mt-1 min-h-11 w-full rounded-lg border border-border bg-white px-3 py-2 text-ui font-normal text-app-text md:min-h-9"
          >
            <option value="all">全部教材</option>
            {keys.map((key) => (
              <option key={key} value={key}>{keyLabel(key)}</option>
            ))}
          </select>
        </label>
        <label className="field-label">
          類型
          <select
            value={selectedType}
            onChange={(event) => setSelectedType(event.target.value)}
            className="mt-1 min-h-11 w-full rounded-lg border border-border bg-white px-3 py-2 text-ui font-normal text-app-text md:min-h-9"
          >
            <option value="all">全部</option>
            <option value="page">頁面截圖 ({filteredCounts.page})</option>
            <option value="image">圖片 ({filteredCounts.image})</option>
            <option value="table">表格 ({filteredCounts.table})</option>
          </select>
        </label>
        <label className="field-label">
          頁碼 / 教材頁碼
          <input
            value={pageQuery}
            onChange={(event) => setPageQuery(event.target.value)}
            placeholder="例如 31 或 3-24"
            className="mt-1 min-h-11 w-full rounded-lg border border-border bg-white px-3 py-2 text-ui font-normal text-app-text md:min-h-9"
          />
        </label>
      </FilterBar>

      <div className="text-ui text-text-light mb-3">
        顯示 {visibleItems.length} / {filtered.length} 項
      </div>

      {filtered.length === 0 && (
        <StatePanel
          tone="empty"
          title="目前篩選沒有圖片或表格"
          className="mb-5"
          action={(
            <button
              type="button"
              onClick={() => {
                setSelectedKey('all')
                setSelectedLevel('all')
                setSelectedType('all')
                setPageQuery('')
              }}
              className="btn-outline"
            >
              清除篩選
            </button>
          )}
        >
          目前篩選沒有圖片或表格。請清除篩選，或改選其他學習指引、公告試題或官方參考資料。
        </StatePanel>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {visibleItems.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={(event) => {
              lightboxTriggerRef.current = event.currentTarget
              setActive(item)
            }}
            className="min-h-11 text-left bg-card rounded-xl shadow-sm border border-border overflow-hidden transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
          >
            <div className="h-52 bg-unanswered-soft flex items-center justify-center overflow-hidden">
              <AssetPreview item={item} />
            </div>
            <div className="p-3">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold text-primary">{item.level ? `${item.level} ` : ''}{keyLabel(item.key)}</span>
                <span className="badge badge-accent shrink-0">
                  {typeLabel(item.type)}
                </span>
              </div>
              <div className="text-meta text-text-light">
                {pageText(item)}
              </div>
            </div>
          </button>
        ))}
      </div>

      {visibleItems.length < filtered.length && (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            className="btn-outline min-w-40"
            onClick={() => setVisibleCount((count) => Math.min(count + PAGE_SIZE, filtered.length))}
          >
            載入更多（尚有 {filtered.length - visibleItems.length} 項）
          </button>
        </div>
      )}

      <Dialog
        open={Boolean(active)}
        title="教材圖片與表格"
        onClose={() => setActive(null)}
        initialFocusRef={lightboxCloseRef}
        restoreFocusRef={lightboxTriggerRef}
        className="flex h-[100dvh] flex-col rounded-none sm:h-auto sm:max-h-[92dvh] sm:max-w-6xl sm:rounded-xl"
      >
        {active && (
          <>
            <div className="p-4 border-b border-border flex items-start justify-between gap-3">
              <div>
                <div className="font-semibold text-primary">{active.level ? `${active.level} ` : ''}{keyLabel(active.key)}</div>
                <div className="text-meta text-text-light">
                  {typeLabel(active.type)} · {pageText(active)}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-meta tabular-nums text-text-light">
                  {activeIndex >= 0 ? activeIndex + 1 : 0} / {filtered.length}
                </span>
                <button
                  ref={lightboxCloseRef}
                  type="button"
                  onClick={() => setActive(null)}
                  className="btn-outline btn-sm"
                >
                  關閉 (Esc)
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto bg-unanswered-soft p-4">
              <img
                src={publicAsset(active.path)}
                alt={assetAlt(active)}
                className="mx-auto max-w-full h-auto bg-white"
              />
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-border p-3">
              <button
                type="button"
                onClick={() => goRelative(-1)}
                disabled={activeIndex <= 0}
                className="btn-outline btn-sm"
              >
                ‹ 上一項
              </button>
              <button
                type="button"
                onClick={() => goRelative(1)}
                disabled={activeIndex === -1 || activeIndex >= filtered.length - 1}
                className="btn-outline btn-sm"
              >
                下一項 ›
              </button>
            </div>
          </>
        )}
      </Dialog>
    </div>
  )
}
