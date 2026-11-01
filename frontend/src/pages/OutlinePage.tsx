import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { loadGuideSearchIndex } from '../data/guideSearch'
import { resourceLevels } from '../data/resourceRegistry'
import type { GuideSearchIndexData, GuideSearchNode } from '../types'
import { PageHeader, StatePanel, SubjectPicker, subjectOptionById } from '../components/ui'
import { navLabel } from '../constants/navLabels'

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
            <div className="flex items-start gap-1">
              {children.length > 0 ? (
                <button
                  type="button"
                  onClick={() => onToggle(node.id)}
                  aria-expanded={!isCollapsed}
                  aria-label={isCollapsed ? '展開' : '收合'}
                  className="-ml-2 inline-flex min-h-[var(--control-min-h)] min-w-[var(--control-min-h)] shrink-0 items-center justify-center rounded-md text-ui text-text-light hover:bg-accent-soft hover:text-accent"
                >
                  {isCollapsed ? '▸' : '▾'}
                </button>
              ) : (
                <span className="-ml-2 min-w-[var(--control-min-h)] shrink-0" aria-hidden="true" />
              )}
              {to ? (
                <Link to={to} className={`inline-flex min-h-[var(--control-min-h)] items-center py-1 text-body leading-6 no-underline hover:text-accent ${weight}`}>
                  {node.t}
                </Link>
              ) : (
                <span className="inline-flex min-h-[var(--control-min-h)] items-center py-1 text-body leading-6 text-text-light">{node.t}</span>
              )}
              {children.length > 0 && (
                <span className="shrink-0 self-center text-caption text-text-light">{children.length}</span>
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
  const [loadError, setLoadError] = useState<string | null>(null)
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    let active = true
    setLoadError(null)
    loadGuideSearchIndex()
      .then((loaded) => {
        if (active) setIndex(loaded)
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      active = false
    }
  }, [])

  const subjects = useMemo(
    () =>
      resourceLevels.flatMap((level) =>
        level.subjects
          .filter((subject) => index?.guides[subject.id])
          .map((subject) => subject.id),
      ),
    [index],
  )

  const activeId = subjectId ?? subjects[0]
  const activeSubject = activeId ? subjectOptionById(activeId) : undefined
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
      <PageHeader
        className="mb-5"
        title={navLabel('outline')}
        description="全部章、節與內文標題，點擊直接跳到對應段落。"
        meta={guide && <span className="pill">{guide.nodes.length} 個項目</span>}
      />

      <section className="surface mb-4 p-4">
        {subjects.length > 0 ? (
          <SubjectPicker
            value={activeId ?? null}
            onChange={setSubjectId}
            subjectIds={subjects}
          />
        ) : (
          <div className="field-label">科目</div>
        )}
        <p className="mt-2 text-meta leading-6 text-text-light">
          {index ? `${subjects.length} 個科目可瀏覽；選擇科目後會保留章節樹狀結構。` : '目錄資料載入中'}
        </p>
      </section>

      {loadError && (
        <StatePanel tone="error" title="目錄載入失敗" className="mb-4">
          {loadError}
        </StatePanel>
      )}

      {!index && !loadError && (
        <StatePanel tone="loading" className="mb-4">
          載入目錄中…
        </StatePanel>
      )}

      {index && subjects.length === 0 && (
        <StatePanel tone="empty" title="沒有可顯示的目錄" className="mb-4">
          目前資源清單中沒有對應的學習指引目錄。
        </StatePanel>
      )}

      {guide && tree && (
        <div className="surface p-4 sm:p-5">
          <h2 className="section-title mb-3">{activeSubject?.fullLabel ?? '學習指引'}目錄</h2>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-outline btn-sm"
              onClick={() => setCollapsed(new Set())}
            >
              全部展開
            </button>
            <button
              type="button"
              className="btn-outline btn-sm"
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
