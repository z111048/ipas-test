import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import guideImagesRaw from '../generated/guideImages.json'
import juniorTocRaw from '@data/toc_manifest.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import { resourceSummary } from '../data/resourceRegistry'
import type { GuideImageAsset, GuideImagesData, TocManifest } from '../types'
import { publicAsset } from '../utils/assets'

const guideImages = guideImagesRaw as unknown as GuideImagesData
const juniorToc = juniorTocRaw as unknown as TocManifest
const middleToc = middleTocRaw as unknown as TocManifest

interface ChapterMeta {
  title: string
  subjectId: string
  subjectLabel: string
  subjectShort: string
  level: string
  order: number
}

const chapterMeta: Record<string, ChapterMeta> = {}
const subjectMeta: Record<string, { label: string; short: string; level: string; order: number }> = {}

function indexToc(toc: TocManifest, levelLabel: string) {
  toc.subjects.forEach((subject, si) => {
    const short = subject.subject.split('：')[0]
    subjectMeta[subject.id] = { label: subject.subject, short, level: levelLabel, order: si }
    subject.chapters.forEach((chapter, ci) => {
      chapterMeta[chapter.id] = {
        title: chapter.title,
        subjectId: subject.id,
        subjectLabel: subject.subject,
        subjectShort: short,
        level: levelLabel,
        order: si * 1000 + ci,
      }
    })
  })
}

indexToc(juniorToc, '初級')
indexToc(middleToc, '中級')

const PAGE_STEP = 6

interface ChapterGroup {
  chapterId: string
  meta: ChapterMeta
  images: GuideImageAsset[]
}

function headingTrail(image: GuideImageAsset) {
  const path = image.headingPath ?? []
  if (path.length <= 1) return ''
  return path.slice(0, -1).join(' › ')
}

export default function VisualCardsPage() {
  const [searchParams] = useSearchParams()
  const queryString = searchParams.toString()
  const [level, setLevel] = useState(searchParams.get('level') ?? '初級')
  const [subjectId, setSubjectId] = useState(searchParams.get('subject') ?? 'all')
  const [chapterId, setChapterId] = useState(searchParams.get('chapter') ?? 'all')
  const [keyword, setKeyword] = useState('')
  const [visibleGroups, setVisibleGroups] = useState(PAGE_STEP)
  const [active, setActive] = useState<GuideImageAsset | null>(null)

  useEffect(() => {
    setLevel(searchParams.get('level') ?? '初級')
    setSubjectId(searchParams.get('subject') ?? 'all')
    setChapterId(searchParams.get('chapter') ?? 'all')
  }, [queryString])

  const total = guideImages.images.length

  const subjects = useMemo(() => {
    const ids = Array.from(
      new Set(
        guideImages.images
          .filter((image) => level === 'all' || image.level === level)
          .map((image) => image.subjectId),
      ),
    )
    return ids
      .filter((id) => subjectMeta[id])
      .sort((a, b) => subjectMeta[a].order - subjectMeta[b].order)
  }, [level])

  const chapters = useMemo(() => {
    const ids = Array.from(
      new Set(
        guideImages.images
          .filter((image) => level === 'all' || image.level === level)
          .filter((image) => subjectId === 'all' || image.subjectId === subjectId)
          .map((image) => image.sourceNodeId),
      ),
    )
    return ids
      .filter((id) => chapterMeta[id])
      .sort((a, b) => chapterMeta[a].order - chapterMeta[b].order)
  }, [level, subjectId])

  const groups = useMemo<ChapterGroup[]>(() => {
    const kw = keyword.trim().toLowerCase()
    const filtered = guideImages.images.filter((image) => {
      if (level !== 'all' && image.level !== level) return false
      if (subjectId !== 'all' && image.subjectId !== subjectId) return false
      if (chapterId !== 'all' && image.sourceNodeId !== chapterId) return false
      if (kw) {
        const haystack = `${image.title} ${(image.headingPath ?? []).join(' ')}`.toLowerCase()
        if (!haystack.includes(kw)) return false
      }
      return true
    })

    const byChapter = new Map<string, GuideImageAsset[]>()
    for (const image of filtered) {
      const list = byChapter.get(image.sourceNodeId)
      if (list) list.push(image)
      else byChapter.set(image.sourceNodeId, [image])
    }

    return Array.from(byChapter.entries())
      .filter(([id]) => chapterMeta[id])
      .map(([id, images]) => ({ chapterId: id, meta: chapterMeta[id], images }))
      .sort((a, b) => a.meta.order - b.meta.order)
  }, [level, subjectId, chapterId, keyword])

  const matchedCount = useMemo(() => groups.reduce((sum, group) => sum + group.images.length, 0), [groups])

  useEffect(() => {
    setVisibleGroups(PAGE_STEP)
  }, [level, subjectId, chapterId, keyword])

  const shownGroups = groups.slice(0, visibleGroups)
  const hasMore = visibleGroups < groups.length

  return (
    <div className="page-shell">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Concept cards</div>
        <h1 className="text-[1.55rem] leading-tight font-bold text-primary mb-1">概念圖卡</h1>
        <p className="text-[0.92rem] leading-7 text-text-light max-w-3xl">
          把學習指引的每個重點整理成一張張圖卡，依章節編排、少量多餐。零碎時間滑幾張，就能把抽象概念
          記得更牢；點開任一張可放大細看。
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="pill">共 {total} 張圖卡</span>
          {resourceSummary.visuals?.byLevel &&
            Object.entries(resourceSummary.visuals.byLevel).map(([lv, count]) => (
              <span key={lv} className="pill pill-muted">
                {lv} {count} 張
              </span>
            ))}
        </div>
      </div>

      <div className="surface p-4 mb-5">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <label className="text-[0.82rem] text-text-light">
            等級
            <select
              value={level}
              onChange={(event) => {
                setLevel(event.target.value)
                setSubjectId('all')
                setChapterId('all')
              }}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部等級</option>
              <option value="初級">初級</option>
              <option value="中級">中級</option>
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            科目
            <select
              value={subjectId}
              onChange={(event) => {
                setSubjectId(event.target.value)
                setChapterId('all')
              }}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部科目</option>
              {subjects.map((id) => (
                <option key={id} value={id}>
                  {subjectMeta[id].short}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            章節
            <select
              value={chapterId}
              onChange={(event) => setChapterId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            >
              <option value="all">全部章節</option>
              {chapters.map((id) => (
                <option key={id} value={id}>
                  {chapterMeta[id].title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[0.82rem] text-text-light">
            關鍵字
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜尋圖卡標題"
              className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-app-text"
            />
          </label>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <div className="text-[0.85rem] text-text-light">
            篩選出 {matchedCount} 張圖卡，分布於 {groups.length} 個章節
          </div>
          {(level !== '初級' || subjectId !== 'all' || chapterId !== 'all' || keyword) && (
            <button
              type="button"
              onClick={() => {
                setLevel('初級')
                setSubjectId('all')
                setChapterId('all')
                setKeyword('')
              }}
              className="rounded-lg border border-accent px-3 py-1.5 text-[0.82rem] text-accent transition-colors hover:bg-accent hover:text-white"
            >
              重設篩選
            </button>
          )}
        </div>
      </div>

      {groups.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-6 text-center text-text-light">
          目前篩選沒有圖卡，請放寬條件或重設篩選。
        </div>
      )}

      <div className="space-y-8">
        {shownGroups.map((group) => (
          <section key={group.chapterId}>
            <div className="mb-3 flex items-end justify-between gap-3 border-b border-border pb-2">
              <div>
                <div className="text-[0.72rem] uppercase tracking-wider text-text-light">
                  {group.meta.level} · {group.meta.subjectShort}
                </div>
                <h2 className="text-[1.05rem] font-semibold text-primary">{group.meta.title}</h2>
              </div>
              <span className="pill shrink-0">{group.images.length} 張</span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {group.images.map((image) => (
                <VisualCard key={image.id} image={image} onOpen={() => setActive(image)} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {hasMore && (
        <div className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={() => setVisibleGroups((value) => value + PAGE_STEP)}
            className="btn-outline"
          >
            載入更多章節（剩 {groups.length - visibleGroups} 章）
          </button>
        </div>
      )}

      {active && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4"
          onClick={() => setActive(null)}
        >
          <div
            className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-card"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border p-4">
              <div className="min-w-0">
                <div className="truncate font-semibold text-primary">{active.title}</div>
                <div className="text-[0.8rem] text-text-light">
                  {chapterMeta[active.sourceNodeId]?.level} · {chapterMeta[active.sourceNodeId]?.subjectShort} ·{' '}
                  {chapterMeta[active.sourceNodeId]?.title}
                </div>
                {headingTrail(active) && (
                  <div className="mt-0.5 text-[0.76rem] text-text-light">{headingTrail(active)}</div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setActive(null)}
                className="shrink-0 rounded-lg border border-border px-3 py-1 text-sm hover:border-accent"
              >
                關閉
              </button>
            </div>
            <div className="overflow-auto bg-[#f5f7fa] p-4">
              <img src={publicAsset(active.src)} alt={active.title} className="mx-auto h-auto max-w-full bg-white" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function VisualCard({ image, onOpen }: { image: GuideImageAsset; onOpen: () => void }) {
  const [failed, setFailed] = useState(false)
  const trail = headingTrail(image)
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
    >
      <div className="flex h-48 items-center justify-center overflow-hidden bg-[#f5f7fa] p-2">
        {failed ? (
          <span className="px-4 text-center text-xs text-text-light">圖卡載入失敗</span>
        ) : (
          <img
            src={publicAsset(image.src)}
            alt={image.title}
            loading="lazy"
            onError={() => setFailed(true)}
            className="max-h-full max-w-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
          />
        )}
      </div>
      <div className="border-t border-border p-3">
        {trail && <div className="mb-0.5 truncate text-[0.72rem] text-text-light">{trail}</div>}
        <div className="line-clamp-2 text-[0.86rem] font-medium leading-snug text-primary">{image.title}</div>
      </div>
    </button>
  )
}
