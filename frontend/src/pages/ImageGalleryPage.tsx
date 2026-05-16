import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import pdfGallery from '../generated/pdfGallery.json'
import type { PdfImageAsset, PdfImageGallery } from '../types'

const assetBase = import.meta.env.BASE_URL.replace(/\/$/, '')

function publicAsset(path: string) {
  return `${assetBase}${path.startsWith('/') ? path : `/${path}`}`
}

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

function AssetPreview({ item }: { item: PdfImageAsset }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="h-full w-full flex items-center justify-center px-4 text-center text-sm text-red-700 bg-red-50">
        圖片載入失敗：{item.path}
      </div>
    )
  }

  return (
    <img
      src={publicAsset(item.path)}
      alt={`${item.key} ${item.type} ${item.page_number}`}
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
  const [active, setActive] = useState<PdfImageAsset | null>(null)

  useEffect(() => {
    setSelectedLevel(searchParams.get('level') ?? 'all')
    setSelectedKey(searchParams.get('key') ?? 'all')
    setSelectedType(searchParams.get('type') ?? 'all')
    setPageQuery(searchParams.get('page') ?? '')
    setActive(null)
  }, [queryString])

  const levels = useMemo(() => {
    const unique = Array.from(new Set(gallery.items.map((item) => item.level).filter(Boolean))) as string[]
    return unique.sort((a, b) => a.localeCompare(b, 'zh-Hant'))
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

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">PDF 圖片與表格檢視</div>
      <div className="text-text-light mb-5">
        檢視逐頁抽取時裁切出的圖片與表格，共 {counts.total} 項
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <label className="text-[0.82rem] text-text-light">
            等級
            <select
              value={selectedLevel}
              onChange={(event) => {
                setSelectedLevel(event.target.value)
                setSelectedKey('all')
              }}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部等級</option>
              {levels.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            PDF
            <select
              value={selectedKey}
              onChange={(event) => setSelectedKey(event.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部 PDF</option>
              {keys.map((key) => (
                <option key={key} value={key}>{keyLabels[key] ?? key}</option>
              ))}
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            類型
            <select
              value={selectedType}
              onChange={(event) => setSelectedType(event.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部</option>
              <option value="page">頁面截圖 ({filteredCounts.page})</option>
              <option value="image">圖片 ({filteredCounts.image})</option>
              <option value="table">表格 ({filteredCounts.table})</option>
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            頁碼 / PDF 標籤
            <input
              value={pageQuery}
              onChange={(event) => setPageQuery(event.target.value)}
              placeholder="例如 31 或 3-24"
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={() => {
                setSelectedKey('all')
                setSelectedLevel('all')
                setSelectedType('all')
                setPageQuery('')
              }}
              className="w-full rounded-lg border border-accent px-3 py-2 text-accent hover:bg-accent hover:text-white transition-colors"
            >
              清除篩選
            </button>
          </div>
        </div>
      </div>

      <div className="text-[0.88rem] text-text-light mb-3">
        顯示 {filtered.length} 項
      </div>

      {filtered.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-6 text-center text-text-light">
          目前篩選沒有圖片或表格。請清除篩選，或改選其他學習指引、公告試題或官方參考資料。
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setActive(item)}
            className="text-left bg-card rounded-xl shadow-sm border border-border overflow-hidden hover:border-accent hover:shadow-md transition-all"
          >
            <div className="h-52 bg-[#f5f7fa] flex items-center justify-center overflow-hidden">
              <AssetPreview item={item} />
            </div>
            <div className="p-3">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold text-primary">{item.level ? `${item.level} ` : ''}{keyLabels[item.key] ?? item.key}</span>
                <span className="text-[0.74rem] rounded-full bg-[#eef5ff] text-accent px-2 py-0.5">
                  {item.type === 'page' ? '頁面' : item.type === 'table' ? '表格' : '圖片'}
                </span>
              </div>
              <div className="text-[0.78rem] text-text-light">
                Page {item.page_number}{item.page_label ? ` / ${item.page_label}` : ''} · {item.asset_id}
              </div>
            </div>
          </button>
        ))}
      </div>

      {active && (
        <div
          className="fixed inset-0 z-[80] bg-black/70 p-4 flex items-center justify-center"
          onClick={() => setActive(null)}
        >
          <div
            className="bg-card rounded-xl max-w-6xl max-h-[92vh] w-full overflow-hidden flex flex-col"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="p-4 border-b border-border flex items-start justify-between gap-3">
              <div>
                <div className="font-semibold text-primary">{active.level ? `${active.level} ` : ''}{keyLabels[active.key] ?? active.key}</div>
                <div className="text-[0.82rem] text-text-light">
                  {active.type === 'page' ? '頁面' : active.type === 'table' ? '表格' : '圖片'} · Page {active.page_number}
                  {active.page_label ? ` / ${active.page_label}` : ''} · bbox [{active.bbox.join(', ')}]
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActive(null)}
                className="rounded-lg border border-border px-3 py-1 text-sm hover:border-accent"
              >
                關閉
              </button>
            </div>
            <div className="p-4 overflow-auto bg-[#f5f7fa]">
              <img
                src={publicAsset(active.path)}
                alt={active.id}
                className="mx-auto max-w-full h-auto bg-white"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
