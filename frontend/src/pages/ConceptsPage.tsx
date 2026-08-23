import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FilterBar, PageHeader, SegmentedControl, StatePanel } from '../components/ui'

// three.js 約 1MB：只有切到立體圖才載
const ConceptGraph3D = lazy(() => import('../components/concepts/ConceptGraph3D'))
const QuestionModal = lazy(() => import('../components/concepts/QuestionModal'))
// 圖例要跟立體圖上的顏色一致：那是深色底的色階（暗→亮＝考得少→考得多）
const HEAT_STEPS = ['#184f95', '#256abf', '#3987e5', '#6da7ec', '#b7d3f6']

interface GlossaryRef {
  level: string
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
  name: string
  parent: string
  questionCount: { official: number; practice: number }
  glossary: GlossaryRef[]
  chapters: ChapterRef[]
  related: { name: string; weight: number }[]
  questions: QuestionRef[]
}

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

  const selectedName = searchParams.get('c') ?? ''
  const concepts = graph?.concepts ?? []
  const selected = concepts.find((c) => c.name === selectedName) ?? null

  const parents = useMemo(
    () => Array.from(new Set(concepts.map((c) => c.parent).filter(Boolean))).sort(),
    [concepts]
  )

  const listed = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return concepts.filter((concept) => {
      if (parent !== 'all' && concept.parent !== parent) return false
      if (!keyword) return true
      return [concept.name, concept.parent, concept.glossary[0]?.en ?? '',
        concept.glossary[0]?.definition ?? '']
        .join(' ').toLowerCase().includes(keyword)
    })
  }, [concepts, query, parent])

  function select(name: string) {
    const next = new URLSearchParams(searchParams)
    next.set('c', name)
    setSearchParams(next)
  }

  if (loadError) {
    return (
      <div className="page-shell">
        <StatePanel tone="error" title="概念索引載入失敗">
          {loadError}
        </StatePanel>
      </div>
    )
  }

  if (!graph) {
    return (
      <div className="page-shell">
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
        eyebrow="概念索引"
        title="概念、定義與考過的題目"
        description={
          <>
            {graph.conceptCount} 個概念，串起名詞定義、學習指引章節、
            {graph.questionCount.official} 題歷屆試題與 {graph.questionCount.practice} 題練習。
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
        <label className="block">
          <span className="mb-1.5 block text-[0.78rem] font-semibold text-text-light">分類</span>
          <select
            value={parent}
            onChange={(event) => setParent(event.target.value)}
            className="min-h-11 w-full rounded-lg border border-border px-3 py-2 text-[0.88rem] outline-none focus:border-accent"
          >
            <option value="all">全部分類（{concepts.length}）</option>
            {parents.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[0.78rem] font-semibold text-text-light">搜尋</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋概念、英文或定義"
            className="min-h-11 w-full rounded-lg border border-border px-3 py-2 text-[0.88rem] outline-none focus:border-accent"
          />
        </label>
        <SegmentedControl
          className="md:col-span-2"
          label="檢視模式"
          value={view}
          onChange={(value) => setView(value as typeof view)}
          options={[
            { value: 'list', label: '清單' },
            { value: 'graph', label: '立體圖' },
          ]}
        />
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
                selected={selectedName}
                minWeight={strongOnly ? 2 : 1}
                onSelect={select}
              />
            </Suspense>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.78rem] text-text-light">
            <span className="flex items-center gap-1">
              考古題題數
              {HEAT_STEPS.map((color) => (
                <span
                  key={color}
                  className="inline-block h-3 w-5 rounded-[2px]"
                  style={{ backgroundColor: color }}
                />
              ))}
            <span>少 → 多</span>
            </span>
            <span>球體大小＝總題數（考古題＋練習）</span>
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

      <div className={`grid grid-cols-1 gap-4 ${view === 'list' ? 'lg:grid-cols-[280px_1fr]' : ''}`}>
        <div
          className={`bg-card rounded-xl shadow-sm border border-border overflow-hidden max-h-[70dvh] overflow-y-auto ${
            view === 'graph' ? 'hidden' : ''
          }`}
        >
          {listed.map((concept) => {
            return (
              <button
                key={concept.name}
                type="button"
                onClick={() => select(concept.name)}
                className={`min-h-11 w-full text-left px-4 py-2.5 border-b border-border cursor-pointer ${
                  concept.name === selectedName ? 'bg-accent/10' : 'hover:bg-[#f7fbff]'
                }`}
              >
                <div className="text-[0.9rem] font-semibold text-primary">{concept.name}</div>
                <div className="text-[0.75rem] text-text-light">
                  {concept.parent} · 考古題 {concept.questionCount.official}／練習 {concept.questionCount.practice}
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

        <div className="bg-card rounded-xl shadow-sm border border-border p-5">
          {!selected ? (
            <StatePanel tone="empty">
              從概念清單挑一個概念，或在立體圖中點選節點。
            </StatePanel>
          ) : (
            <>
              <div className="text-[0.75rem] text-text-light">{selected.parent}</div>
              <h2 className="text-xl font-bold text-primary mt-1 mb-2">{selected.name}</h2>

              {selected.glossary.length > 0 ? (
                selected.glossary.map((entry) => (
                  <div key={`${entry.level}-${entry.subjectName}`} className="mb-3">
                    <div className="text-[0.78rem] text-accent">
                      {entry.level} · {entry.en}
                    </div>
                    <p className="leading-7 content-justify m-0">{entry.definition}</p>
                    {entry.example && (
                      <p className="leading-7 content-justify m-0 mt-1 text-text-light text-[0.85rem]">
                        例：{entry.example}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-[0.85rem] text-text-light">這個概念還沒有名詞解釋。</p>
              )}

              {selected.chapters.length > 0 && (
                <div className="mt-4">
                  <div className="text-[0.8rem] font-semibold text-primary mb-1.5">學習指引章節</div>
                  <div className="flex flex-wrap gap-2">
                    {selected.chapters.map((chapter) => (
                      <span
                        key={chapter.nodeId}
                        className="rounded border border-border px-2 py-1 text-[0.78rem] text-text-light"
                      >
                        {chapter.guideKey.split('-')[0]} {chapter.nodeId}（{chapter.count} 題）
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selected.related.length > 0 && (
                <div className="mt-4">
                  <div className="text-[0.8rem] font-semibold text-primary mb-1.5">
                    常一起出現的概念
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selected.related.map((item) => (
                      <button
                        key={item.name}
                        type="button"
                        onClick={() => select(item.name)}
                        className="min-h-11 rounded-full border border-border px-3 py-2 text-[0.8rem] text-primary hover:border-accent cursor-pointer"
                      >
                        {item.name}
                        <span className="text-text-light"> ×{item.weight}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4">
                <div className="text-[0.8rem] font-semibold text-primary mb-1.5">
                  考過這個概念的題目（{selected.questions.length} 題）
                </div>
                <ul className="m-0 list-none p-0 space-y-1.5">
                  {selected.questions.map((question) => (
                    <li key={`${question.source}-${question.id}`}>
                      <button
                        type="button"
                        onClick={() => setOpenQuestion(question)}
                        className="min-h-11 w-full rounded-lg border border-border px-3 py-2 text-left text-[0.85rem] hover:border-accent cursor-pointer"
                      >
                        <span className="text-text-light text-[0.75rem]">
                          {question.level} · {question.source}
                        </span>
                        <br />
                        <span className="text-primary">{question.stem}…</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>

      {openQuestion && (
        <Suspense fallback={null}>
          <QuestionModal item={openQuestion} onClose={() => setOpenQuestion(null)} />
        </Suspense>
      )}
    </div>
  )
}
