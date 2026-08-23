import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loadMindmap, loadMindmapIndex } from '../data/guideMindmap'
import type { GuideMindmapData, GuideMindmapIndex, GuideMindmapNode } from '../types'
import { FilterBar, PageHeader, SegmentedControl, StatePanel } from '../components/ui'

const TopicHeatPanel = lazy(() => import('../components/guide/TopicHeatPanel'))

/** 兩個軸：章節（哪一章考得多）與概念（哪個觀念反覆出現）。 */
type Axis = 'chapter' | 'topic'
type Metric = 'questions' | 'density'

const ROW = 46
const COL = 250
const PAD_X = 24
const PAD_Y = 28

interface Placed {
  node: GuideMindmapNode
  x: number
  y: number
}

/**
 * 橫向樹狀布局：depth 決定 x，葉節點依序佔一列、父節點取子節點的中點。
 * 座標一律在前端算——展開狀態與視窗寬度都會變，寫進資料檔就固定住了。
 */
function layout(data: GuideMindmapData) {
  const byId = new Map(data.nodes.map((node) => [node.i, node]))
  const childrenOf = new Map<string | null, GuideMindmapNode[]>()
  for (const node of data.nodes) {
    const list = childrenOf.get(node.p) ?? []
    list.push(node)
    childrenOf.set(node.p, list)
  }

  const placed: Placed[] = []
  let row = 0

  const walk = (node: GuideMindmapNode): number => {
    const children = childrenOf.get(node.i) ?? []
    const depth = node.d - 1
    if (children.length === 0) {
      const y = PAD_Y + row * ROW
      row += 1
      placed.push({ node, x: PAD_X + depth * COL, y })
      return y
    }
    const ys = children.map(walk)
    const y = (ys[0] + ys[ys.length - 1]) / 2
    placed.push({ node, x: PAD_X + depth * COL, y })
    return y
  }

  for (const rootId of data.rootIds) {
    const root = byId.get(rootId)
    if (root) walk(root)
  }

  const edges = placed.flatMap(({ node, x, y }) => {
    const parent = node.p ? placed.find((item) => item.node.i === node.p) : undefined
    return parent ? [{ id: node.i, x1: parent.x, y1: parent.y, x2: x, y2: y }] : []
  })

  const width = PAD_X * 2 + COL * Math.max(...placed.map((p) => p.node.d))
  const height = PAD_Y * 2 + row * ROW
  return { placed, edges, width, height }
}

function valueOf(node: GuideMindmapNode, metric: Metric) {
  return metric === 'questions' ? node.q : node.y
}

export default function MindmapPage() {
  const navigate = useNavigate()
  const [index, setIndex] = useState<GuideMindmapIndex | null>(null)
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [data, setData] = useState<GuideMindmapData | null>(null)
  const [indexError, setIndexError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)
  const [metric, setMetric] = useState<Metric>('questions')
  const [axis, setAxis] = useState<Axis>('chapter')

  useEffect(() => {
    let active = true
    setIndexError(null)
    loadMindmapIndex()
      .then((loaded) => {
        if (!active) return
        setIndex(loaded)
        setSubjectId((current) => current ?? loaded.guides[0]?.subjectId ?? null)
      })
      .catch((error) => {
        if (active) setIndexError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!subjectId) return
    let active = true
    setData(null)
    setDataError(null)
    loadMindmap(subjectId)
      .then((loaded) => {
        if (active) setData(loaded)
      })
      .catch((error) => {
        if (active) setDataError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      active = false
    }
  }, [subjectId])

  const view = useMemo(() => (data ? layout(data) : null), [data])
  const peak = useMemo(() => {
    if (!data) return 0
    const values = data.nodes.map((node) => valueOf(node, metric) ?? 0)
    return Math.max(...values, 1)
  }, [data, metric])

  const ranking = useMemo(() => {
    if (!data) return []
    return data.nodes
      .filter((node) => valueOf(node, metric) !== null)
      .sort((a, b) => (valueOf(b, metric) ?? 0) - (valueOf(a, metric) ?? 0))
      .slice(0, 8)
  }, [data, metric])

  return (
    <div className="page-shell mx-auto w-full max-w-6xl">
      <PageHeader
        className="mb-5"
        eyebrow="知識探索"
        title={axis === 'chapter' ? '章節熱度圖' : '概念熱度'}
        description={
          axis === 'chapter'
            ? '以歷屆試題實際命中的章節統計，節點越大代表該章考得越多。點擊節點可直接前往該章。'
            : '以歷屆試題實際考到的觀念統計，看哪個觀念反覆出現、又散落在哪幾章。'
        }
      />

      <SegmentedControl
        className="mb-4"
        label="熱度統計軸"
        value={axis}
        onChange={(value) => setAxis(value as Axis)}
        options={[
          { value: 'chapter', label: '按章節' },
          { value: 'topic', label: '按概念' },
        ]}
      />

      {axis === 'topic' ? (
        <div className="space-y-4">
          <StatePanel tone="status">
            手機版可先查看高頻概念摘要；詳細表格若超出畫面，可在區塊內橫向捲動。
          </StatePanel>
          <Suspense
            fallback={
              <StatePanel tone="loading">
                載入概念熱度中…
              </StatePanel>
            }
          >
            <div className="w-full max-w-full overflow-x-auto">
              <TopicHeatPanel />
            </div>
          </Suspense>
        </div>
      ) : (
        <ChapterHeatView
          index={index}
          indexError={indexError}
          subjectId={subjectId}
          setSubjectId={setSubjectId}
          data={data}
          dataError={dataError}
          view={view}
          peak={peak}
          ranking={ranking}
          metric={metric}
          setMetric={setMetric}
          navigate={navigate}
        />
      )}
    </div>
  )
}

interface ChapterHeatViewProps {
  index: GuideMindmapIndex | null
  indexError: string | null
  subjectId: string | null
  setSubjectId: (id: string) => void
  data: GuideMindmapData | null
  dataError: string | null
  view: ReturnType<typeof layout> | null
  peak: number
  ranking: GuideMindmapNode[]
  metric: Metric
  setMetric: (metric: Metric) => void
  navigate: (to: string) => void
}

function ChapterHeatView({
  index,
  indexError,
  subjectId,
  setSubjectId,
  data,
  dataError,
  view,
  peak,
  ranking,
  metric,
  setMetric,
  navigate,
}: ChapterHeatViewProps) {
  return (
    <>
      <FilterBar
        className="mb-4"
        title="熱度篩選"
        result={data ? `${data.subject}・${data.nodes.length} 個節點` : '資料載入中'}
      >
        <div className="md:col-span-2 xl:col-span-4">
          <div className="mb-1.5 text-[0.78rem] font-semibold text-text-light">科目</div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {index?.guides.map((guide) => (
              <button
                key={guide.subjectId}
                type="button"
                onClick={() => setSubjectId(guide.subjectId)}
                className={`min-h-11 rounded border px-3 py-2 text-sm font-semibold ${
                  guide.subjectId === subjectId
                    ? 'border-accent bg-accent text-white'
                    : 'border-border bg-white text-app-text hover:border-accent'
                }`}
              >
                {guide.level} {guide.subject.replace(/^中級/, '')}
              </button>
            ))}
          </div>
        </div>
        <div className="md:col-span-2 xl:col-span-4">
          <div className="mb-1.5 text-[0.78rem] font-semibold text-text-light">排序依據</div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {(
              [
                ['questions', '題數'],
                ['density', '密度（每千字題數）'],
              ] as [Metric, string][]
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMetric(value)}
                className={`min-h-11 rounded border px-3 py-2 text-sm font-semibold ${
                  metric === value ? 'border-accent text-accent' : 'border-border bg-white text-text-light hover:border-accent'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs leading-6 text-text-light">
            長章節本來就容易累積題數，密度可以看出「單位篇幅」的考點集中程度。
          </p>
        </div>
      </FilterBar>

      {indexError ? (
        <StatePanel tone="error" title="熱度索引載入失敗">
          {indexError}
        </StatePanel>
      ) : index && index.guides.length === 0 ? (
        <StatePanel tone="empty" title="沒有可顯示的熱度資料">
          目前沒有可載入的章節熱度科目。
        </StatePanel>
      ) : dataError ? (
        <StatePanel tone="error" title="章節熱度載入失敗">
          {dataError}
        </StatePanel>
      ) : !view || !data ? (
        <StatePanel tone="loading">
          載入章節熱度中…
        </StatePanel>
      ) : (
        <>
          <StatePanel tone="status" className="mb-4">
            手機版可先用下方熱門章節清單操作；完整圖可在框內橫向捲動，點節點可前往章節。
          </StatePanel>

          <div className="mt-4 w-full max-w-full overflow-x-auto rounded border border-border bg-card">
            <svg
              viewBox={`0 0 ${view.width} ${view.height}`}
              width={view.width}
              height={view.height}
              className="max-w-none"
              role="img"
              aria-label={`${data.subject} 章節熱度圖`}
            >
              {view.edges.map((edge) => (
                <path
                  key={edge.id}
                  d={`M ${edge.x1} ${edge.y1} C ${(edge.x1 + edge.x2) / 2} ${edge.y1}, ${
                    (edge.x1 + edge.x2) / 2
                  } ${edge.y2}, ${edge.x2} ${edge.y2}`}
                  fill="none"
                  className="stroke-border"
                  strokeWidth={1}
                />
              ))}
              {view.placed.map(({ node, x, y }) => {
                const value = valueOf(node, metric)
                const scored = value !== null
                const ratio = scored ? Math.sqrt(value / peak) : 0
                const radius = scored ? 5 + ratio * 13 : 4
                const to = node.r
                return (
                  <g
                    key={node.i}
                    transform={`translate(${x} ${y})`}
                    onClick={() => to && navigate(to)}
                    className={to ? 'cursor-pointer' : undefined}
                  >
                    <circle
                      r={radius}
                      className={scored ? 'fill-accent' : 'fill-none stroke-border'}
                      fillOpacity={scored ? 0.25 + ratio * 0.75 : undefined}
                      strokeWidth={scored ? 0 : 1}
                    />
                    <text
                      x={radius + 6}
                      y={4}
                      className={`text-[12px] ${scored ? 'fill-app-text' : 'fill-text-light'}`}
                    >
                      {node.t.length > 18 ? `${node.t.slice(0, 18)}…` : node.t}
                    </text>
                    <text x={radius + 6} y={17} className="text-[10px] fill-text-light">
                      {node.q === null
                        ? '尚無統計'
                        : `${node.q} 題・${node.y ?? 0}/千字`}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div>
              <h2 className="text-base font-semibold text-primary">熱門章節</h2>
              <ol className="mt-2 space-y-1 text-sm">
                {ranking.map((node, position) => (
                  <li key={node.i} className="flex items-baseline gap-2">
                    <span className="w-5 text-right text-text-light">{position + 1}</span>
                    <button
                      type="button"
                      onClick={() => node.r && navigate(node.r)}
                      className="min-h-11 text-left text-app-text hover:text-accent"
                    >
                      {node.t}
                    </button>
                    <span className="ml-auto text-text-light">
                      {metric === 'questions' ? `${node.q} 題` : `${node.y}/千字`}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
            <div className="text-xs text-text-light">
              <h2 className="text-base font-semibold text-primary">怎麼看這張圖</h2>
              <ul className="mt-2 space-y-1.5">
                <li>
                  統計自 {data.level}
                  歷屆公告試題實際引用到的章節；一題常同時涉及數章，
                  <strong>各章數字不能相加</strong>。
                </li>
                <li>空心節點表示這一層目前還沒有統計資料，不代表沒有考過。</li>
                <li>
                  章節篇幅差距很大（最長的章有三萬多字），只看題數會把「長」讀成「熱」，
                  兩種排序一起看比較準。
                </li>
              </ul>
            </div>
          </div>
        </>
      )}
    </>
  )
}
