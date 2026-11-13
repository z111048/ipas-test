/**
 * 學習指引每章最上方的「本章脈絡」：先看懂一章怎麼串起來，再讀原文。
 * 資料由 scripts/export_context_maps.py 從 data/context_maps/ 驗證後匯出；
 * 每個重點與關係都附原書頁碼與逐字摘句，「看原文」跳到正文對應區塊。
 */
import { Link } from 'react-router-dom'
import { useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { preferredScrollBehavior } from '../../utils/motion'

export interface ContextMapSource { block: number; quote: string; page: number | null }
export interface ContextMapNode {
  id: string
  label: string
  lane: string | null
  parent: string | null
  concept: string | null
  gist: string
  src: ContextMapSource[]
  exam: number
}
export interface ContextMapEdge {
  a: string
  b: string
  kind: 'flow' | 'cross'
  label: string
  block: number
  quote: string
  page: number | null
}
export interface ContextMapData {
  chapter: { guideKey: string; nodeId: string; label: string; subjectId: string; title: string }
  headline: string
  lede: string
  story: { step: string; title: string; text: string }[]
  lanes: { id: string; name: string }[]
  nodes: ContextMapNode[]
  edges: ContextMapEdge[]
  confusions: { a: string; b: string; text: string; blocks: number[]; pages: number[] }[]
  gaps: { name: string; block: number; page: number | null }[]
  examOnly: {
    name: string
    count: number
    mentioned: boolean
    link?: { subjectId: string; chapterId: string; block: number; chapterTitle: string; label: string }
  }[]
  notes: { block: number; page: number | null; text: string }[]
}

// 分區配色：與網站 accent（indigo）同一組飽和度，四色在白底都過 4.5:1。
const LANE_TONES = [
  { dot: 'bg-teal-700', text: 'text-teal-800', ring: 'ring-teal-700', soft: 'bg-teal-50' },
  { dot: 'bg-indigo-700', text: 'text-indigo-800', ring: 'ring-indigo-700', soft: 'bg-indigo-50' },
  { dot: 'bg-orange-700', text: 'text-orange-800', ring: 'ring-orange-700', soft: 'bg-orange-50' },
  { dot: 'bg-purple-700', text: 'text-purple-800', ring: 'ring-purple-700', soft: 'bg-purple-50' },
]

const OPEN_STORAGE_KEY = 'ipas:contextMapOpen'

function readOpenPreference() {
  try {
    return window.localStorage.getItem(OPEN_STORAGE_KEY) !== '0'
  } catch {
    return true
  }
}

function writeOpenPreference(value: boolean) {
  try {
    window.localStorage.setItem(OPEN_STORAGE_KEY, value ? '1' : '0')
  } catch {
    // 私密視窗寫不進去時只是不記得選擇
  }
}

function SourceButton({ page, onClick, label = '看原文' }: { page: number | null; onClick: () => void; label?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-link inline-flex min-h-11 items-center text-meta font-semibold md:min-h-0"
    >
      {label}{page ? `（第 ${page} 頁）` : ''} ↓
    </button>
  )
}

export default function ContextMap({ map, onJump }: { map: ContextMapData; onJump: (block: number) => void }) {
  const [open, setOpen] = useState(readOpenPreference)
  const laneIndex = useMemo(() => Object.fromEntries(map.lanes.map((lane, index) => [lane.id, index])), [map])
  const byId = useMemo(() => Object.fromEntries(map.nodes.map((node) => [node.id, node])), [map])
  const firstPick = useMemo(
    () => [...map.nodes].filter((node) => node.lane !== null).sort((a, b) => b.exam - a.exam)[0]?.id ?? map.nodes[0].id,
    [map],
  )
  const [selectedId, setSelectedId] = useState<string>(firstPick)
  const [touched, setTouched] = useState(false)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const selected = byId[selectedId] ?? byId[firstPick]
  const core = map.nodes.find((node) => node.lane === null)

  // 每個分區內依 parent 排成縮排樹
  const lanes = useMemo(() => map.lanes.map((lane) => {
    const mine = map.nodes.filter((node) => node.lane === lane.id)
    const ids = new Set(mine.map((node) => node.id))
    const ordered: { node: ContextMapNode; depth: number }[] = []
    const visit = (node: ContextMapNode, depth: number) => {
      ordered.push({ node, depth })
      mine.filter((child) => child.parent === node.id).forEach((child) => visit(child, depth + 1))
    }
    mine.filter((node) => !node.parent || !ids.has(node.parent)).forEach((node) => visit(node, 0))
    return { lane, ordered }
  }), [map])

  const related = useMemo(() => {
    const set = new Set<string>([selected.id])
    if (selected.parent) set.add(selected.parent)
    map.nodes.forEach((node) => { if (node.parent === selected.id) set.add(node.id) })
    map.edges.forEach((edge) => {
      if (edge.a === selected.id) set.add(edge.b)
      if (edge.b === selected.id) set.add(edge.a)
    })
    return set
  }, [map, selected])

  const relations = map.edges.filter((edge) => edge.a === selected.id || edge.b === selected.id)
  const children = map.nodes.filter((node) => node.parent === selected.id)
  const parent = selected.parent ? byId[selected.parent] : undefined

  const select = (id: string) => {
    setSelectedId(id)
    setTouched(true)
    // 手機上說明欄在地圖下方，點了之後若看不到就捲過去
    requestAnimationFrame(() => {
      const panel = panelRef.current
      if (!panel) return
      const rect = panel.getBoundingClientRect()
      if (rect.top > window.innerHeight - 120 || rect.bottom < 0) panel.scrollIntoView({ block: 'nearest', behavior: preferredScrollBehavior() })
    })
  }

  const toggle = () => {
    setOpen((value) => {
      writeOpenPreference(!value)
      return !value
    })
  }

  const tone = (node: ContextMapNode) => (node.lane === null ? null : LANE_TONES[laneIndex[node.lane] % LANE_TONES.length])
  const hasExtras = map.confusions.length + map.examOnly.length + map.gaps.length + map.notes.length > 0
  const hotItems = map.examOnly.filter((item) => !item.mentioned)
  // 先列可連到中級說明的，再列題數最多的；其餘收在「還有 N 項」裡，避免清單比地圖還長。
  const HOT_PREVIEW = 8
  const hotSorted = [...hotItems.filter((item) => item.link), ...hotItems.filter((item) => !item.link)]
  const [showAllHot, setShowAllHot] = useState(false)
  const hotShown = showAllHot ? hotSorted : hotSorted.slice(0, Math.max(HOT_PREVIEW, hotItems.filter((item) => item.link).length))

  return (
    <section className="surface mb-4 p-4 sm:p-6" aria-labelledby="context-map-title" data-context-map={map.chapter.nodeId}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="section-title">本章脈絡</div>
          <h2 id="context-map-title" className="mt-1 text-lg font-bold leading-snug text-primary [text-wrap:balance] sm:text-xl">
            {map.headline}
          </h2>
        </div>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls="context-map-body"
          className="btn-secondary shrink-0"
        >
          {open ? '收合' : '展開'}
        </button>
      </div>
      <p className="mt-2 max-w-[44em] text-body text-text-light">{map.lede}</p>

      {open && (
        <div id="context-map-body" className="mt-4 grid gap-6">
          <ol
            className="grid grid-cols-1 overflow-hidden rounded-xl border border-border sm:grid-cols-2 lg:[grid-template-columns:repeat(var(--stops),minmax(0,1fr))]"
            style={{ '--stops': map.story.length } as CSSProperties}
            aria-label="閱讀順序"
          >
            {map.story.map((stop, index) => (
              <li key={index} className="min-w-0 border-b border-border p-3 last:border-b-0 sm:border-r lg:border-b-0 lg:last:border-r-0">
                <div className="text-meta text-text-light">{index + 1}・{stop.step}</div>
                <div className={`font-semibold ${index === map.story.length - 1 ? 'text-accent' : 'text-primary'}`}>{stop.title}</div>
                <p className="mt-0.5 text-meta text-text-light">{stop.text}</p>
              </li>
            ))}
          </ol>

          <div>
            <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="font-semibold text-primary">知識地圖</h3>
              <span className="text-meta text-text-light">點知識點看重點、原文摘句與它連到哪裡</span>
            </div>
            {core && (
              <button
                type="button"
                onClick={() => select(core.id)}
                aria-pressed={selected.id === core.id}
                className={`mb-3 inline-flex min-h-11 items-center gap-2 rounded-full border px-4 py-1 font-bold transition-colors ${selected.id === core.id ? 'border-primary bg-primary text-on-dark' : 'border-border-strong text-primary hover:border-accent'}`}
              >
                <span aria-hidden="true" className="inline-block size-2.5 rounded-full bg-current" />
                {core.label}
              </button>
            )}
            <div
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:[grid-template-columns:repeat(var(--lanes),minmax(0,1fr))]"
              style={{ '--lanes': map.lanes.length } as CSSProperties}
            >
              {lanes.map(({ lane, ordered }, index) => {
                const laneTone = LANE_TONES[index % LANE_TONES.length]
                return (
                  <div key={lane.id} className="min-w-0">
                    <div className={`mb-1.5 flex items-center gap-2 text-meta font-bold ${laneTone.text}`}>
                      <span aria-hidden="true" className={`inline-block size-2.5 rounded-full ${laneTone.dot}`} />
                      {lane.name}
                    </div>
                    <ul className="grid gap-1">
                      {ordered.map(({ node, depth }) => {
                        const isSelected = node.id === selected.id
                        const dim = touched && !related.has(node.id)
                        return (
                          <li key={node.id} style={{ paddingLeft: `${depth * 0.9}rem` }}>
                            <button
                              type="button"
                              onClick={() => select(node.id)}
                              aria-pressed={isSelected}
                              className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-meta transition-[opacity,background-color] md:min-h-9 ${isSelected ? `${laneTone.soft} ring-2 ${laneTone.ring}` : 'hover:bg-panel'} ${dim ? 'opacity-45' : ''}`}
                            >
                              <span aria-hidden="true" className={`inline-block shrink-0 rounded-full ${laneTone.dot} ${depth === 0 ? 'size-2.5' : 'size-1.5'}`} />
                              <span className={`min-w-0 flex-1 ${depth === 0 ? 'font-semibold text-primary' : 'text-app-text'}`}>{node.label}</span>
                              {node.exam > 0 && (
                                <span className="shrink-0 rounded-full bg-warning-soft px-1.5 text-caption leading-5 text-warning-text">
                                  考 {node.exam}
                                </span>
                              )}
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )
              })}
            </div>

            <div ref={panelRef} className="mt-4 scroll-mt-16 rounded-xl border border-border bg-panel p-4" aria-live="polite">
              <div className="flex flex-wrap items-center gap-2 text-meta text-text-light">
                <span className={selected.lane === null ? 'font-semibold text-primary' : `font-semibold ${tone(selected)?.text}`}>
                  {selected.lane === null ? '核心' : map.lanes[laneIndex[selected.lane]].name}
                </span>
                {selected.exam > 0 && (
                  <span className="badge badge-warning">公告試題 {selected.exam} 題</span>
                )}
              </div>
              <h4 className="mt-1 text-base font-bold text-primary">{selected.label}</h4>
              <p className="mt-1 text-body text-app-text">{selected.gist}</p>
              <ul className="mt-2 grid gap-1.5">
                {selected.src.map((source, index) => (
                  <li key={index} className="flex flex-wrap items-baseline gap-x-2 border-l-2 border-border-strong pl-3">
                    <span className="text-meta text-text-light">「{source.quote}」</span>
                    <SourceButton page={source.page} onClick={() => onJump(source.block)} />
                  </li>
                ))}
              </ul>
              {(parent || children.length > 0 || relations.length > 0) && (
                <ul className="mt-3 grid gap-1 border-t border-border pt-3 text-meta">
                  {parent && (
                    <li>
                      <span className="text-text-light">屬於</span>{' '}
                      <button type="button" className="text-link font-semibold" onClick={() => select(parent.id)}>{parent.label}</button>
                    </li>
                  )}
                  {children.length > 0 && (
                    <li>
                      <span className="text-text-light">包含</span>{' '}
                      {children.map((child, index) => (
                        <span key={child.id}>
                          {index > 0 && '、'}
                          <button type="button" className="text-link font-semibold" onClick={() => select(child.id)}>{child.label}</button>
                        </span>
                      ))}
                    </li>
                  )}
                  {relations.map((edge, index) => {
                    const other = byId[edge.a === selected.id ? edge.b : edge.a]
                    return (
                      <li key={index} className="flex flex-wrap items-baseline gap-x-2">
                        <span className={edge.kind === 'cross' ? 'font-semibold text-warning-text' : 'text-text-light'}>
                          {edge.kind === 'cross' ? '跨段落｜' : ''}{edge.label}
                        </span>
                        <button type="button" className="text-link font-semibold" onClick={() => select(other.id)}>{other.label}</button>
                        <SourceButton page={edge.page} onClick={() => onJump(edge.block)} />
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>

          {hasExtras && (
            <div className="grid gap-6">
              {map.confusions.length > 0 && (
                <div>
                  <h3 className="mb-2 font-semibold text-primary">容易搞混的概念</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {map.confusions.map((pair, index) => (
                      <div key={index} className="min-w-0 rounded-xl border border-border p-3">
                        <div className="font-semibold text-primary">
                          {pair.a}<span className="mx-1.5 text-meta font-normal text-text-light">vs</span>{pair.b}
                        </div>
                        <p className="mt-1 text-meta text-app-text">{pair.text}</p>
                        <SourceButton page={pair.pages[0] ?? null} onClick={() => onJump(pair.blocks[0])} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {hotItems.length > 0 && (
                <div>
                  <h3 className="font-semibold text-primary">公告試題常考、本章沒有說明</h3>
                  <p className="mt-1 text-meta text-text-light">
                    歷屆公告試題標到本章至少 3 題，本章正文卻沒有出現這個詞。有連結的，可以到中級學習指引讀對應段落。
                  </p>
                  <ul className="mt-2 flex flex-wrap items-start gap-2">
                    {hotShown.map((item) => (
                      <li key={item.name} className="min-w-0 rounded-lg border border-dashed border-warning-line px-3 py-1.5 text-meta">
                        <span className="font-semibold text-primary">{item.name}</span>
                        <span className="ml-1.5 text-text-light">{item.count} 題</span>
                        {item.link && (
                          <Link
                            to={`/guide/${item.link.subjectId}/${item.link.chapterId}#block-${item.link.block}`}
                            className="text-link ml-2 font-semibold"
                          >
                            中級：{item.link.chapterTitle}›{item.link.label} →
                          </Link>
                        )}
                      </li>
                    ))}
                    {hotShown.length < hotSorted.length && (
                      <li>
                        <button type="button" onClick={() => setShowAllHot(true)} className="text-link inline-flex min-h-11 items-center px-1 text-meta font-semibold md:min-h-0 md:py-1.5">
                          還有 {hotSorted.length - hotShown.length} 項 ▾
                        </button>
                      </li>
                    )}
                  </ul>
                </div>
              )}

              {map.gaps.length > 0 && (
                <div>
                  <h3 className="font-semibold text-primary">章末練習考到、正文沒有說明</h3>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {map.gaps.map((gap) => (
                      <li key={gap.name}>
                        <button
                          type="button"
                          onClick={() => onJump(gap.block)}
                          className="inline-flex min-h-11 items-center rounded-lg border border-border px-3 py-1 text-meta hover:border-accent md:min-h-0"
                        >
                          {gap.name}<span className="ml-1.5 text-text-light">第 {gap.page} 頁 ↓</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {map.notes.length > 0 && (
                <div>
                  <h3 className="font-semibold text-primary">原書疑誤</h3>
                  <p className="mt-1 text-meta text-text-light">已和官方 PDF 核對：原書本身就這樣印。正文照原書刊載，並在該段下方加註。</p>
                  <ul className="mt-2 grid gap-2">
                    {map.notes.map((note) => (
                      <li key={note.block} className="rounded-lg bg-warning-soft px-3 py-2 text-meta text-warning-text">
                        {note.text} <SourceButton page={note.page} onClick={() => onJump(note.block)} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <p className="text-meta text-text-light">
            每個重點都附原書頁碼與原文摘句；「考 N」是歷屆公告試題中標到本章、對應該概念的題數（一題可能對到多個概念，不可相加）。
          </p>
        </div>
      )}
    </section>
  )
}
