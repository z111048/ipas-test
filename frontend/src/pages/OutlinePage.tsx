import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { loadGuideSearchIndex } from '../data/guideSearch'
import { resourceLevels } from '../data/resourceRegistry'
import type { GuideSearchIndexData, GuideSearchNode } from '../types'

/** 由節點陣列建 parent → children 的索引；索引本身是依樹序排好的。 */
function buildTree(nodes: GuideSearchNode[]) {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const childrenOf = new Map<string | null, GuideSearchNode[]>()
  for (const node of nodes) {
    const list = childrenOf.get(node.p) ?? []
    list.push(node)
    childrenOf.set(node.p, list)
  }
  return { byId, childrenOf }
}

function routeFor(node: GuideSearchNode, byId: Map<string, GuideSearchNode>) {
  let current: GuideSearchNode | undefined = node
  while (current) {
    if (current.r) return current.r
    current = current.p ? byId.get(current.p) : undefined
  }
  return undefined
}

function OutlineNodes({
  parentId,
  childrenOf,
  byId,
  collapsed,
  onToggle,
  depth = 0,
}: {
  parentId: string | null
  childrenOf: Map<string | null, GuideSearchNode[]>
  byId: Map<string, GuideSearchNode>
  collapsed: Set<string>
  onToggle: (id: string) => void
  depth?: number
}) {
  const nodes = childrenOf.get(parentId) ?? []
  if (nodes.length === 0) return null

  return (
    <ul className={depth === 0 ? 'space-y-1' : 'ml-3 space-y-0.5 border-l border-border pl-3'}>
      {nodes.map((node) => {
        const children = childrenOf.get(node.id) ?? []
        const isCollapsed = collapsed.has(node.id)
        const base = routeFor(node, byId)
        // a 已保證對應到真的存在的區塊；x=1 表示那是最近的上層標題（近似定位）
        const to = !base ? undefined : node.a ? `${base}#${node.a}` : base
        const weight =
          node.k === 'c' ? 'font-bold text-primary' : node.k === 's' ? 'font-semibold text-primary' : 'text-app-text'

        return (
          <li key={node.id}>
            <div className="flex items-start gap-1.5">
              {children.length > 0 ? (
                <button
                  type="button"
                  onClick={() => onToggle(node.id)}
                  aria-expanded={!isCollapsed}
                  aria-label={isCollapsed ? '展開' : '收合'}
                  className="mt-0.5 w-4 shrink-0 text-[0.7rem] text-text-light hover:text-accent"
                >
                  {isCollapsed ? '▸' : '▾'}
                </button>
              ) : (
                <span className="w-4 shrink-0" aria-hidden="true" />
              )}
              {to ? (
                <Link to={to} className={`text-[0.86rem] leading-6 no-underline hover:text-accent ${weight}`}>
                  {node.t}
                </Link>
              ) : (
                <span className="text-[0.86rem] leading-6 text-text-light">{node.t}</span>
              )}
              {children.length > 0 && (
                <span className="mt-1 shrink-0 text-[0.66rem] text-text-light">{children.length}</span>
              )}
            </div>
            {!isCollapsed && (
              <OutlineNodes
                parentId={node.id}
                childrenOf={childrenOf}
                byId={byId}
                collapsed={collapsed}
                onToggle={onToggle}
                depth={depth + 1}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function OutlinePage() {
  const [index, setIndex] = useState<GuideSearchIndexData | null>(null)
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadGuideSearchIndex().then(setIndex)
  }, [])

  const subjects = useMemo(
    () =>
      resourceLevels.flatMap((level) =>
        level.subjects
          .filter((subject) => index?.guides[subject.id])
          .map((subject) => ({ id: subject.id, label: subject.label, level: level.label })),
      ),
    [index],
  )

  const activeId = subjectId ?? subjects[0]?.id
  const guide = activeId ? index?.guides[activeId] : undefined
  const tree = useMemo(() => (guide ? buildTree(guide.nodes) : null), [guide])

  const toggle = (id: string) =>
    setCollapsed((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // 預設把「節」以下收起來，否則一次攤開三百多列
  useEffect(() => {
    if (!guide) return
    setCollapsed(new Set(guide.nodes.filter((node) => node.k === 's').map((node) => node.id)))
  }, [guide])

  return (
    <div className="page-shell">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">完整目錄</div>
        <h1 className="mb-1 text-2xl font-bold text-primary">學習指引目錄</h1>
        <p className="text-[0.9rem] text-text-light">
          全部章、節與內文標題，點擊直接跳到對應段落。
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {subjects.map((subject) => (
          <button
            key={subject.id}
            type="button"
            onClick={() => setSubjectId(subject.id)}
            className={`rounded-full border px-3 py-1 text-[0.8rem] transition-colors ${
              subject.id === activeId
                ? 'border-accent bg-accent text-white'
                : 'border-border bg-white text-text-light hover:text-accent'
            }`}
          >
            {subject.level}・{subject.label}
          </button>
        ))}
      </div>

      {!index && <p className="text-[0.88rem] text-text-light">載入目錄中…</p>}

      {guide && tree && (
        <div className="surface p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className="pill">{guide.nodes.length} 個項目</span>
            <button
              type="button"
              className="text-[0.78rem] text-accent hover:underline"
              onClick={() => setCollapsed(new Set())}
            >
              全部展開
            </button>
            <button
              type="button"
              className="text-[0.78rem] text-accent hover:underline"
              onClick={() =>
                setCollapsed(new Set(guide.nodes.filter((node) => node.k !== 'h').map((node) => node.id)))
              }
            >
              全部收合
            </button>
          </div>
          <OutlineNodes
            parentId={null}
            childrenOf={tree.childrenOf}
            byId={tree.byId}
            collapsed={collapsed}
            onToggle={toggle}
          />
        </div>
      )}
    </div>
  )
}
