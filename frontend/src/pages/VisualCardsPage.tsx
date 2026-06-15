import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeRaw from 'rehype-raw'
import rehypeKatex from 'rehype-katex'
import guideImagesRaw from '../generated/guideImages.json'
import juniorTocRaw from '@data/toc_manifest.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import { resourceSummary } from '../data/resourceRegistry'
import type { GuideContent, GuideImageAsset, GuideImagesData, TocManifest } from '../types'
import { publicAsset } from '../utils/assets'

const guideImages = guideImagesRaw as unknown as GuideImagesData
const juniorToc = juniorTocRaw as unknown as TocManifest
const middleToc = middleTocRaw as unknown as TocManifest

const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')

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

function normalizeHeading(text: string) {
  return text
    .replace(/^[#＃\s]+/, '')
    .replace(/^\d+(?:[.\-]\d+)*\s*/, '')
    .replace(/[\s　]/g, '')
    .replace(/[：:]+$/, '')
    .toLowerCase()
}

/** Slice the markdown section under the heading matching the image's concept title. */
function extractSection(content: string, rawTitle: string): string | null {
  const target = normalizeHeading(rawTitle)
  if (!target) return null
  const lines = content.split('\n')
  let startIdx = -1
  let startLevel = 0
  for (let i = 0; i < lines.length; i += 1) {
    const match = lines[i].match(/^(#{1,6})\s+(.*)$/)
    if (!match) continue
    const heading = normalizeHeading(match[2])
    if (!heading) continue
    const fuzzy = target.length >= 3 && (heading.includes(target) || target.includes(heading))
    if (heading === target || fuzzy) {
      startIdx = i
      startLevel = match[1].length
      break
    }
  }
  if (startIdx === -1) return null
  const out = [lines[startIdx]]
  for (let i = startIdx + 1; i < lines.length; i += 1) {
    const match = lines[i].match(/^(#{1,6})\s+/)
    if (match && match[1].length <= startLevel) break
    out.push(lines[i])
  }
  return out.join('\n').trim() || null
}

/** Fallback bite-sized intro: the chapter lead text before the first sub-heading. */
function chapterIntro(content: string, limit = 360): string {
  const lines = content.split('\n')
  const body: string[] = []
  let started = false
  for (const line of lines) {
    const isHeading = /^#{1,6}\s+/.test(line)
    if (!started) {
      if (/^#\s+/.test(line)) {
        started = true
        continue
      }
      if (line.trim()) started = true
    }
    if (started && isHeading) break
    if (started) body.push(line)
  }
  const text = body.join('\n').trim()
  if (text.length <= limit) return text
  return `${text.slice(0, limit).replace(/\s+\S*$/, '')}…`
}

const markdownComponents = {
  h1: ({ children }: { children?: ReactNode }) => (
    <h3 className="mb-2 text-base font-semibold text-primary break-words">{children}</h3>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h3 className="mt-3 mb-1.5 text-base font-semibold text-primary break-words">{children}</h3>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h4 className="mt-3 mb-1 text-[0.95rem] font-semibold text-accent break-words">{children}</h4>
  ),
  h4: ({ children }: { children?: ReactNode }) => (
    <h5 className="mt-2.5 mb-1 text-[0.9rem] font-semibold text-primary break-words">{children}</h5>
  ),
  h5: ({ children }: { children?: ReactNode }) => (
    <h6 className="mt-2 mb-1 text-[0.86rem] font-semibold text-app-text break-words">{children}</h6>
  ),
  h6: ({ children }: { children?: ReactNode }) => (
    <h6 className="mt-2 mb-1 text-[0.84rem] font-semibold text-text-light break-words">{children}</h6>
  ),
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-2.5 break-words leading-7">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2.5 list-disc list-outside space-y-1 pl-5">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2.5 list-decimal list-outside space-y-1 pl-5">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="break-words leading-7">{children}</li>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="my-3 overflow-x-auto">
      <table className="table-soft text-[0.82rem]">{children}</table>
    </div>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="whitespace-pre-line break-words leading-6">{children}</td>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="whitespace-pre-line break-words">{children}</th>
  ),
  code: ({ children }: { children?: ReactNode }) => (
    <code className="break-words rounded bg-[#eef2f7] px-1 py-0.5 text-[0.82rem]">{children}</code>
  ),
}

interface SectionState {
  loading: boolean
  markdown: string
  isIntro: boolean
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
  const [section, setSection] = useState<SectionState>({ loading: false, markdown: '', isIntro: false })

  useEffect(() => {
    setLevel(searchParams.get('level') ?? '初級')
    setSubjectId(searchParams.get('subject') ?? 'all')
    setChapterId(searchParams.get('chapter') ?? 'all')
  }, [queryString])

  // Lazy-load the chapter content and slice out the section for the opened card.
  useEffect(() => {
    if (!active) {
      setSection({ loading: false, markdown: '', isIntro: false })
      return
    }
    let cancelled = false
    setSection({ loading: true, markdown: '', isIntro: false })
    const moduleKey = `../generated/guideContent/${active.level}-${active.guideKey}/${active.sourceNodeId}.json`
    const loader = guideContentModules[moduleKey]
    if (!loader) {
      setSection({ loading: false, markdown: '', isIntro: false })
      return
    }
    loader()
      .then((module) => {
        if (cancelled) return
        const content = module.default?.content ?? ''
        const matched = extractSection(content, active.title)
        if (matched) {
          setSection({ loading: false, markdown: matched, isIntro: false })
        } else {
          setSection({ loading: false, markdown: chapterIntro(content), isIntro: true })
        }
      })
      .catch(() => {
        if (!cancelled) setSection({ loading: false, markdown: '', isIntro: false })
      })
    return () => {
      cancelled = true
    }
  }, [active])

  // Lock body scroll while the reader modal is open.
  useEffect(() => {
    if (!active) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [active])

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
              <div className="min-w-0">
                <div className="text-[0.72rem] uppercase tracking-wider text-text-light">
                  {group.meta.level} · {group.meta.subjectShort}
                </div>
                <h2 className="break-words text-[1.05rem] font-semibold text-primary">{group.meta.title}</h2>
              </div>
              <span className="pill shrink-0">{group.images.length} 張</span>
            </div>
            <div className="grid grid-cols-1 justify-items-center gap-4 sm:grid-cols-2 sm:justify-items-stretch xl:grid-cols-3">
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
                <div className="break-words text-[0.95rem] font-semibold leading-snug text-primary">{active.title}</div>
                <div className="mt-0.5 break-words text-[0.8rem] text-text-light">
                  {chapterMeta[active.sourceNodeId]?.level} · {chapterMeta[active.sourceNodeId]?.subjectShort} ·{' '}
                  {chapterMeta[active.sourceNodeId]?.title}
                </div>
                {headingTrail(active) && (
                  <div className="mt-0.5 break-words text-[0.76rem] text-text-light">{headingTrail(active)}</div>
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

            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="flex items-center justify-center bg-[#f5f7fa] p-4">
                <img
                  src={publicAsset(active.src)}
                  alt={active.title}
                  className="mx-auto max-h-[42vh] w-auto max-w-full bg-white object-contain"
                />
              </div>

              <div className="p-4 sm:p-5">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
                  <span className="text-[0.8rem] font-semibold text-primary">
                    {section.isIntro ? '本章重點摘要' : '本段章節內容'}
                  </span>
                </div>

                {section.loading ? (
                  <div className="py-4 text-[0.85rem] text-text-light">章節內容載入中…</div>
                ) : section.markdown ? (
                  <div className="prose prose-sm max-w-none break-words text-[0.86rem] leading-7 text-app-text">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeRaw, rehypeKatex]}
                      components={markdownComponents}
                    >
                      {section.markdown}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="py-2 text-[0.85rem] text-text-light">此圖卡目前沒有對應的章節文字，可前往完整章節閱讀。</div>
                )}

                <div className="mt-4 border-t border-border pt-3">
                  <Link
                    to={`/guide/${active.subjectId}/${active.sourceNodeId}`}
                    onClick={() => setActive(null)}
                    className="btn-outline"
                  >
                    前往完整章節 →
                  </Link>
                </div>
              </div>
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
      className="group flex w-full max-w-sm flex-col overflow-hidden rounded-xl border border-border bg-card text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md sm:max-w-none"
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
        <div className="line-clamp-2 break-words text-[0.86rem] font-medium leading-snug text-primary">{image.title}</div>
      </div>
    </button>
  )
}
