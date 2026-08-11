import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

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
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [parent, setParent] = useState('all')
  const [view, setView] = useState<'list' | 'graph'>('list')
  const [openQuestion, setOpenQuestion] = useState<QuestionRef | null>(null)
  const [showWeakLinks, setShowWeakLinks] = useState(false)

  useEffect(() => {
    import('../generated/conceptGraph.json').then((module) => {
      setGraph(module.default as unknown as ConceptGraph)
    })
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

  if (!graph) {
    return <p className="text-sm text-text-light">載入中…</p>
  }

  return (
    <div>
      <div className="text-[0.78rem] font-semibold text-accent mb-1">概念索引</div>
      <div className="text-2xl font-bold text-primary mb-1">概念、定義與考過的題目</div>
      <div className="text-text-light mb-5">
        {graph.conceptCount} 個概念，串起名詞定義、學習指引章節、
        {graph.questionCount.official} 題歷屆試題與 {graph.questionCount.practice} 題練習。
        點任一概念看它考在哪裡、和哪些概念一起出現。
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          <select
            value={parent}
            onChange={(event) => setParent(event.target.value)}
            className="rounded-lg border border-border px-3 py-2 text-[0.88rem] outline-none focus:border-accent"
          >
            <option value="all">全部分類（{concepts.length}）</option>
            {parents.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋概念、英文或定義"
            className="w-full lg:w-[280px] rounded-lg border border-border px-3 py-2 text-[0.88rem] outline-none focus:border-accent"
          />
          <div className="lg:ml-auto flex gap-2">
            {([['list', '清單'], ['graph', '立體圖']] as [typeof view, string][]).map(
              ([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setView(value)}
                  className={`px-3 py-2 rounded-lg border text-[0.85rem] cursor-pointer ${
                    view === value
                      ? 'border-accent bg-accent text-white'
                      : 'border-border bg-white text-primary hover:border-accent'
                  }`}
                >
                  {label}
                </button>
              )
            )}
          </div>
        </div>
      </div>

      {view === 'graph' && (
        <div className="mb-4">
          <Suspense fallback={<p className="text-sm text-text-light">載入立體圖…</p>}>
            <ConceptGraph3D
              concepts={listed}
              selected={selectedName}
              minWeight={showWeakLinks ? 1 : 2}
              onSelect={select}
            />
          </Suspense>
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
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={showWeakLinks}
                onChange={(event) => setShowWeakLinks(event.target.checked)}
              />
              顯示只同題出現過一次的弱關聯
            </label>
            <span>拖曳旋轉、滾輪縮放、點球體看內容</span>
          </div>
        </div>
      )}

      <div className={`grid grid-cols-1 gap-4 ${view === 'list' ? 'lg:grid-cols-[280px_1fr]' : ''}`}>
        <div
          className={`bg-card rounded-xl shadow-sm border border-border overflow-hidden max-h-[70vh] overflow-y-auto ${
            view === 'graph' ? 'hidden' : ''
          }`}
        >
          {listed.map((concept) => {
            return (
              <button
                key={concept.name}
                type="button"
                onClick={() => select(concept.name)}
                className={`w-full text-left px-4 py-2.5 border-b border-border cursor-pointer ${
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
            <div className="p-4 text-[0.85rem] text-text-light">找不到符合條件的概念。</div>
          )}
        </div>

        <div className="bg-card rounded-xl shadow-sm border border-border p-5">
          {!selected ? (
            <p className="text-sm text-text-light">從左邊挑一個概念。</p>
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
                        className="rounded-full border border-border px-3 py-1 text-[0.8rem] text-primary hover:border-accent cursor-pointer"
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
                        className="w-full rounded-lg border border-border px-3 py-2 text-left text-[0.85rem] hover:border-accent cursor-pointer"
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
