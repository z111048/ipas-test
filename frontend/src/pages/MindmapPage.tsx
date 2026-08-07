import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loadMindmap, loadMindmapIndex } from '../data/guideMindmap'
import type { GuideMindmapData, GuideMindmapIndex, GuideMindmapNode } from '../types'

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
  const [metric, setMetric] = useState<Metric>('questions')

  useEffect(() => {
    loadMindmapIndex().then((loaded) => {
      setIndex(loaded)
      setSubjectId((current) => current ?? loaded.guides[0]?.subjectId ?? null)
    })
  }, [])

  useEffect(() => {
    if (!subjectId) return
    let active = true
    loadMindmap(subjectId).then((loaded) => {
      if (active) setData(loaded)
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
    <div className="mx-auto w-full max-w-6xl">
      <h1 className="text-2xl font-bold text-primary">章節熱度圖</h1>
      <p className="mt-2 text-sm text-text-light">
        以歷屆試題實際命中的章節統計，節點越大代表該章考得越多。點擊節點可直接前往該章。
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {index?.guides.map((guide) => (
          <button
            key={guide.subjectId}
            type="button"
            onClick={() => setSubjectId(guide.subjectId)}
            className={`rounded border px-3 py-1.5 text-sm ${
              guide.subjectId === subjectId
                ? 'border-accent bg-accent text-white'
                : 'border-border text-app-text'
            }`}
          >
            {guide.level} {guide.subject.replace(/^中級/, '')}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-text-light">排序依據</span>
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
            className={`rounded border px-2.5 py-1 ${
              metric === value ? 'border-accent text-accent' : 'border-border text-text-light'
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-xs text-text-light">
          長章節本來就容易累積題數，密度可以看出「單位篇幅」的考點集中程度。
        </span>
      </div>

      {!view || !data ? (
        <p className="mt-8 text-sm text-text-light">載入中…</p>
      ) : (
        <>
          <div className="mt-4 overflow-x-auto rounded border border-border bg-card">
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
                      className="text-left text-app-text hover:text-accent"
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
    </div>
  )
}
