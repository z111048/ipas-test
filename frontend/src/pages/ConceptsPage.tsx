import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Chip, ChipGroup, Dialog, FilterBar, PageHeader, StatePanel, SubjectPicker, subjectOptions } from '../components/ui'
import { navLabel } from '../constants/navLabels'
import { resolveConcept } from '../data/conceptLookup'
import { guideNav } from '../data/guideNav'
import { useMediaQuery, WIDE_LAYOUT_QUERY } from '../hooks/useMediaQuery'

// three.js 約 1MB：只有切到立體圖才載
const ConceptGraph3D = lazy(() => import('../components/concepts/ConceptGraph3D'))
const QuestionModal = lazy(() => import('../components/concepts/QuestionModal'))
// 圖例要跟立體圖上的顏色一致：那是深色底的色階（暗→亮＝考得少→考得多）
const HEAT_STEPS = ['#184f95', '#256abf', '#3987e5', '#6da7ec', '#b7d3f6']

// 桌機兩欄都固定在 main 頂端、各自捲動
const STICKY_MAX_H = 'lg:max-h-[calc(100dvh-var(--app-header-h)-2rem)]'

interface GlossaryRef {
  level: string
  subject?: string
  subjectName: string
  en: string
  definition: string
  example: string
}

interface ChapterRef {
  nodeId: string
  count: number
  guideKey: string
}

function chapterNode(nodeId: string) {
  for (const guide of Object.values(guideNav.guides)) {
    const node = guide.nodesById[nodeId]
    if (node) return node
  }
  return undefined
}

function chapterSubjectId(nodeId: string) {
  for (const [subjectId, guide] of Object.entries(guideNav.guides)) {
    if (guide.nodesById[nodeId]) return subjectId
  }
  return undefined
}

/** 概念涉及的科目：名詞解釋所屬科目、練習題科目、學習指引章節所屬科目。 */
function conceptSubjectIds(concept: Concept) {
  const ids = new Set<string>()
  for (const entry of concept.glossary) if (entry.subject) ids.add(entry.subject)
  for (const question of concept.questions) if (question.subjectId) ids.add(question.subjectId)
  for (const chapter of concept.chapters) {
    const subjectId = chapterSubjectId(chapter.nodeId)
    if (subjectId) ids.add(subjectId)
  }
  return ids
}

interface QuestionRef {
  id: string
  level: string
  source: string
  route: string
  stem: string
  kind?: 'exam' | 'practice'
  examKey?: string
  subjectId?: string
  chapterId?: string
  practiceSet?: string
}

interface Concept {
  /** 詞彙表的穩定 id（`topic-<8 hex>`）：網址、選取與 key 都用它 */
  id: string
  name: string
  /** id 指派帳本裡的舊正式名稱，只給舊連結解析用 */
  previousNames: string[]
  parent: string
  questionCount: { official: number; practice: number }
  glossary: GlossaryRef[]
  chapters: ChapterRef[]
  related: { id: string; name: string; weight: number }[]
  questions: QuestionRef[]
}

// 舊連結相容層：`?c=` 在 LP-210C 之前放的是中文名稱。解析順序與相容期的說明見 data/conceptLookup.ts；
// 命中舊形式就把網址改寫成 id（下方 useEffect），之後再分享出去的連結不再綁名稱，概念改名也不會斷。

interface ConceptGraph {
  conceptCount: number
  questionCount: { official: number; practice: number }
  edgeCount: number
  concepts: Concept[]
}

export default function ConceptsPage() {
  // 784KB：靜態 import 會把它壓進首頁 bundle，改成進頁面才載
  const [graph, setGraph] = useState<ConceptGraph | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [parent, setParent] = useState('all')
  const [subject, setSubject] = useState('all')
  const [view, setView] = useState<'list' | 'graph'>('list')
  const [openQuestion, setOpenQuestion] = useState<QuestionRef | null>(null)
  const [strongOnly, setStrongOnly] = useState(false)

  useEffect(() => {
    let active = true
    setLoadError(null)
    import('../generated/conceptGraph.json')
      .then((module) => {
        if (active) setGraph(module.default as unknown as ConceptGraph)
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      active = false
    }
  }, [])

  const requested = searchParams.get('c') ?? ''
  const concepts = graph?.concepts ?? []
  const selected = useMemo(() => resolveConcept(concepts, requested), [concepts, requested])
  // 資料載好了、網址有指定、卻對不到任何概念：多半是改名或合併後的失效連結
  const unresolved = graph !== null && requested !== '' && selected === null

  useEffect(() => {
    // 舊形式（中文名稱）命中就改寫成 id；replace 不留歷史紀錄，返回鍵不會卡在舊網址
    if (!selected || requested === selected.id) return
    const next = new URLSearchParams(searchParams)
    next.set('c', selected.id)
    setSearchParams(next, { replace: true })
  }, [requested, selected, searchParams, setSearchParams])

  const parents = useMemo(
    () => Array.from(new Set(concepts.map((c) => c.parent).filter(Boolean))).sort(),
    [concepts]
  )

  const subjectsByConcept = useMemo(
    () => new Map(concepts.map((concept) => [concept.id, conceptSubjectIds(concept)])),
    [concepts]
  )
  const subjectIds = useMemo(() => {
    const present = new Set<string>()
    for (const ids of subjectsByConcept.values()) for (const id of ids) present.add(id)
    return subjectOptions().map((option) => option.id).filter((id) => present.has(id))
  }, [subjectsByConcept])

  const listed = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return concepts.filter((concept) => {
      if (parent !== 'all' && concept.parent !== parent) return false
      if (subject !== 'all' && !subjectsByConcept.get(concept.id)?.has(subject)) return false
      if (!keyword) return true
      return [concept.name, concept.parent, concept.glossary[0]?.en ?? '',
        concept.glossary[0]?.definition ?? '']
        .join(' ').toLowerCase().includes(keyword)
    })
  }, [concepts, query, parent, subject, subjectsByConcept])

  const isDesktop = useMediaQuery(WIDE_LAYOUT_QUERY)
  const detailRef = useRef<HTMLDivElement>(null)
  // 只在使用者主動點選時才捲動；深連結進來或改寫網址不捲
  const scrollOnSelect = useRef(false)

  function select(id: string) {
    scrollOnSelect.current = true
    const next = new URLSearchParams(searchParams)
    next.set('c', id)
    setSearchParams(next)
  }

  const closeDetail = useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('c')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const selectedId = selected?.id
  useEffect(() => {
    const panel = detailRef.current
    if (!panel || !selectedId) return
    // 桌機詳情欄自己捲動：換概念時回到頂端
    panel.scrollTop = 0
    if (scrollOnSelect.current && view === 'graph') {
      // 立體圖模式詳情在圖下方，點了球體要讓它出現在畫面上
      panel.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'nearest',
      })
    }
    scrollOnSelect.current = false
  }, [selectedId, view])

  if (loadError) {
    return (
      <div className="page-shell">
        <PageHeader className="mb-5" title={navLabel('concepts')} />
        <StatePanel tone="error" title="概念索引載入失敗">
          {loadError}
        </StatePanel>
      </div>
    )
  }

  if (!graph) {
    return (
      <div className="page-shell">
        <PageHeader className="mb-5" title={navLabel('concepts')} />
        <StatePanel tone="loading">
          載入概念索引中…
        </StatePanel>
      </div>
    )
  }

  return (
    <div className="page-shell">
      <PageHeader
        className="mb-5"
        title={navLabel('concepts')}
        description={
          <>
            概念、定義與考過的題目：
            {graph.conceptCount} 個概念，串起名詞定義、學習指引章節、
            {graph.questionCount.official} 題公告試題與 {graph.questionCount.practice} 題練習。
            點任一概念看它考在哪裡、和哪些概念一起出現。
          </>
        }
        meta={
          <>
            <span className="pill">{listed.length} 個符合條件</span>
            <span className="pill pill-muted">{graph.edgeCount} 條關聯</span>
          </>
        }
      />

      <FilterBar
        className="mb-4"
        title="概念篩選"
        result={`${listed.length} / ${concepts.length} 個概念`}
      >
        <SubjectPicker
          className="md:col-span-2 xl:col-span-4"
          value={subject}
          onChange={setSubject}
          subjectIds={subjectIds}
          allOption={{ value: 'all', label: '全部科目' }}
        />
        <ChipGroup label="分類" className="md:col-span-2 xl:col-span-4">
          <Chip active={parent === 'all'} onClick={() => setParent('all')}>全部分類</Chip>
          {parents.map((name) => (
            <Chip key={name} active={parent === name} onClick={() => setParent(name)}>{name}</Chip>
          ))}
        </ChipGroup>
        <label className="block md:col-span-2">
          <span className="field-label">搜尋</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋概念、英文或定義"
            className="min-h-11 w-full rounded-lg border border-border px-3 py-2 text-reading outline-none focus:border-accent"
          />
        </label>
        <ChipGroup label="檢視模式" className="md:col-span-2">
          <Chip active={view === 'list'} onClick={() => setView('list')}>清單</Chip>
          <Chip active={view === 'graph'} onClick={() => setView('graph')}>立體圖</Chip>
        </ChipGroup>
      </FilterBar>

      {view === 'graph' && (
        <div className="surface mb-4 overflow-hidden p-4">
          <StatePanel tone="status" className="mb-3">
            立體圖可拖曳旋轉、滾輪縮放、點球體看內容；手機版建議先用搜尋或分類縮小範圍。
          </StatePanel>
          <div className="min-h-[320px] overflow-hidden rounded-lg border border-border bg-[#081526] sm:min-h-[520px]">
            <Suspense
              fallback={
                <StatePanel tone="loading" className="m-3">
                  載入立體圖中…
                </StatePanel>
              }
            >
              <ConceptGraph3D
                concepts={listed}
                selected={selected?.id ?? ''}
                minWeight={strongOnly ? 2 : 1}
                onSelect={select}
              />
            </Suspense>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-meta text-text-light">
            <span className="flex items-center gap-1">
              公告試題題數
              {HEAT_STEPS.map((color) => (
                <span
                  key={color}
                  className="inline-block h-3 w-5 rounded-[2px]"
                  style={{ backgroundColor: color }}
                />
              ))}
              <span>少 → 多</span>
            </span>
            <span>球體大小＝總題數（公告試題＋練習）</span>
            <span>連線＝兩個概念被標在同一題上，粗細＝次數</span>
            <label className="flex min-h-11 items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={strongOnly}
                onChange={(event) => setStrongOnly(event.target.checked)}
              />
              只看強關聯（同題出現 ≥2 次）
            </label>
            <span>拖曳旋轉、滾輪縮放、點球體看內容</span>
          </div>
        </div>
      )}

      <div className={`grid grid-cols-1 gap-4 ${view === 'list' ? 'lg:grid-cols-[280px_minmax(0,1fr)]' : ''}`}>
        <div
          className={`bg-card rounded-xl shadow-sm border border-border overflow-hidden max-h-[70dvh] overflow-y-auto ${
            view === 'graph' ? 'hidden' : `lg:sticky lg:top-4 lg:self-start ${STICKY_MAX_H}`
          }`}
        >
          {listed.map((concept) => {
            return (
              <button
                key={concept.id}
                type="button"
                onClick={() => select(concept.id)}
                aria-current={concept.id === selected?.id ? 'true' : undefined}
                className={`min-h-11 w-full text-left px-4 py-2.5 border-b border-border cursor-pointer ${
                  concept.id === selected?.id ? 'bg-answered-soft' : 'hover:bg-unanswered-soft'
                }`}
              >
                <div className="text-body font-semibold text-primary">{concept.name}</div>
                <div className="text-caption text-text-light">
                  {concept.parent} · 公告試題 {concept.questionCount.official}／練習 {concept.questionCount.practice}
                </div>
              </button>
            )
          })}
          {listed.length === 0 && (
            <StatePanel tone="empty" title="找不到符合條件的概念" className="m-4">
              請調整分類或搜尋關鍵字。
            </StatePanel>
          )}
        </div>

        {isDesktop ? (
          <div
            ref={detailRef}
            className={`bg-card rounded-xl shadow-sm border border-border p-5 ${
              view === 'list' ? `lg:sticky lg:top-4 lg:self-start lg:overflow-y-auto ${STICKY_MAX_H}` : 'scroll-mt-4'
            }`}
          >
            {unresolved ? (
              <UnresolvedConcept requested={requested} />
            ) : !selected ? (
              <StatePanel tone="empty">
                從概念清單挑一個概念，或在立體圖中點選節點。
              </StatePanel>
            ) : (
              <ConceptDetail concept={selected} onSelect={select} onOpenQuestion={setOpenQuestion} />
            )}
          </div>
        ) : (
          unresolved && (
            <div className="order-first">
              <UnresolvedConcept requested={requested} />
            </div>
          )
        )}
      </div>

      {/* 手機：點概念後從底部滑出詳情；開題目彈窗時先收起，關掉題目再回到這個概念 */}
      {!isDesktop && selected && (
        <Dialog
          // 換概念（點「常一起出現的概念」）時重掛面板，捲動位置回到頂端
          key={selected.id}
          open={!openQuestion}
          title={selected.name}
          onClose={closeDetail}
          className="pb-[env(safe-area-inset-bottom)]"
        >
          <ConceptDetail
            concept={selected}
            onSelect={select}
            onOpenQuestion={setOpenQuestion}
            sheet
            onClose={closeDetail}
          />
        </Dialog>
      )}

      {openQuestion && (
        <Suspense fallback={null}>
          <QuestionModal item={openQuestion} onClose={() => setOpenQuestion(null)} />
        </Suspense>
      )}
    </div>
  )
}

function UnresolvedConcept({ requested }: { requested: string }) {
  return (
    <StatePanel tone="empty" title="找不到概念">
      網址指定的「{requested}」不在目前的概念索引裡，可能已改名或合併。
      請從清單重新選一個概念。
    </StatePanel>
  )
}

interface ConceptDetailProps {
  concept: Concept
  onSelect: (id: string) => void
  onOpenQuestion: (question: QuestionRef) => void
  /** 手機底部面板：標題列固定在面板頂端，右側放關閉鈕 */
  sheet?: boolean
  onClose?: () => void
}

function ConceptDetail({
  concept: selected,
  onSelect: select,
  onOpenQuestion: setOpenQuestion,
  sheet = false,
  onClose,
}: ConceptDetailProps) {
  return (
    <>
      {sheet ? (
        <div className="sticky top-0 z-10 flex items-start gap-3 border-b border-border bg-card px-4 pb-3 pt-4">
          <div className="min-w-0 flex-1">
            <div className="text-caption text-text-light">{selected.parent}</div>
            <h2 className="text-xl font-bold text-primary mt-1">{selected.name}</h2>
          </div>
          <button type="button" className="btn-secondary btn-sm shrink-0" onClick={onClose}>
            關閉
          </button>
        </div>
      ) : (
        <>
          <div className="text-caption text-text-light">{selected.parent}</div>
          <h2 className="text-xl font-bold text-primary mt-1 mb-2">{selected.name}</h2>
        </>
      )}
      <div className={sheet ? 'px-4 pb-5 pt-3' : ''}>
        {selected.glossary.length > 0 ? (
          selected.glossary.map((entry) => (
            <div key={`${entry.level}-${entry.subjectName}`} className="mb-3">
              <div className="text-meta text-accent">
                {entry.level} · {entry.en}
              </div>
              <p className="text-reading leading-7 content-justify m-0">{entry.definition}</p>
              {entry.example && (
                <p className="leading-7 content-justify m-0 mt-1 text-text-light text-ui">
                  例：{entry.example}
                </p>
              )}
            </div>
          ))
        ) : (
          <p className="text-ui text-text-light">這個概念還沒有定義說明。</p>
        )}

        {selected.chapters.length > 0 && (
          <div className="mt-4">
            <h3 className="text-meta font-semibold text-primary mb-1.5">{navLabel('guide')}章節</h3>
            <div className="flex flex-wrap gap-2">
              {selected.chapters.map((chapter) => {
                const node = chapterNode(chapter.nodeId)
                const label = `${chapter.guideKey.split('-')[0]} ${node?.title ?? '學習指引'}（${chapter.count} 題）`
                return node?.route ? (
                  <Chip key={chapter.nodeId} to={node.route}>{label}</Chip>
                ) : (
                  <span key={chapter.nodeId} className="badge">{label}</span>
                )
              })}
            </div>
          </div>
        )}

        {selected.related.length > 0 && (
          <div className="mt-4">
            <h3 className="text-meta font-semibold text-primary mb-1.5">
              常一起出現的概念
            </h3>
            <div className="flex flex-wrap gap-2">
              {selected.related.map((item) => (
                <Chip key={item.id} onClick={() => select(item.id)} count={`×${item.weight}`}>
                  {item.name}
                </Chip>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4">
          <h3 className="text-meta font-semibold text-primary mb-1.5">
            考過這個概念的題目（{selected.questions.length} 題）
          </h3>
          <ul className="m-0 list-none p-0 space-y-1.5">
            {selected.questions.map((question) => (
              <li key={`${question.source}-${question.id}`}>
                <button
                  type="button"
                  onClick={() => setOpenQuestion(question)}
                  className="min-h-11 w-full rounded-lg border border-border px-3 py-2 text-left text-ui hover:border-accent cursor-pointer"
                >
                  <span className="text-text-light text-caption">
                    {question.level} · {question.source}
                  </span>
                  <br />
                  <span className="text-primary">{question.stem}…</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  )
}
