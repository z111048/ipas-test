import { Link, NavLink } from 'react-router-dom'
import type { GuideOutlineNode } from '../../types'

interface GuideOutlineTreeProps {
  subjectId: string
  rootIds: string[]
  nodesById: Record<string, GuideOutlineNode>
  activeId?: string
  variant?: 'panel' | 'sidebar'
  onNavigate?: () => void
}

export default function GuideOutlineTree({
  subjectId,
  rootIds,
  nodesById,
  activeId,
  variant = 'panel',
  onNavigate,
}: GuideOutlineTreeProps) {
  return (
    <div className={variant === 'sidebar' ? 'space-y-0.5' : 'space-y-2'}>
      {rootIds.map((nodeId) => (
        <GuideOutlineTreeNode
          key={nodeId}
          subjectId={subjectId}
          nodeId={nodeId}
          nodesById={nodesById}
          activeId={activeId}
          variant={variant}
          onNavigate={onNavigate}
        />
      ))}
    </div>
  )
}

function GuideOutlineTreeNode({
  subjectId,
  nodeId,
  nodesById,
  activeId,
  variant,
  onNavigate,
}: {
  subjectId: string
  nodeId: string
  nodesById: Record<string, GuideOutlineNode>
  activeId?: string
  variant: 'panel' | 'sidebar'
  onNavigate?: () => void
}) {
  const node = nodesById[nodeId]
  if (!node) return null

  const label = `${node.number ? `${node.number} ` : ''}${node.title}`
  const to = `/guide/${subjectId}/${node.id}`
  const pageRange = `PDF 第 ${node.pageRange[0]}–${node.pageRange[1]} 頁`

  if (variant === 'sidebar') {
    return (
      <div>
        <NavLink
          to={to}
          className={({ isActive }) =>
            `block min-h-11 py-2 pr-4 cursor-pointer text-meta border-l-[3px] transition-all duration-150 no-underline ${
              isActive || activeId === node.id
                ? 'bg-chrome-active border-l-accent text-chrome-active-text font-semibold'
                : 'border-l-transparent text-chrome-muted hover:bg-chrome-hover hover:text-chrome-text'
            }`
          }
          style={{ paddingLeft: `${1 + (node.depth - 1) * 0.9}rem` }}
          onClick={onNavigate}
        >
          <span className="block truncate">{label}</span>
          <span className="block text-caption text-text-light mt-0.5">{pageRange}</span>
        </NavLink>
        {node.children.map((childId) => (
          <GuideOutlineTreeNode
            key={childId}
            subjectId={subjectId}
            nodeId={childId}
            nodesById={nodesById}
            activeId={activeId}
            variant={variant}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    )
  }

  const isActive = activeId === node.id
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to={to}
          className={`inline-flex min-h-11 items-center text-body font-semibold no-underline md:min-h-0 ${
            isActive ? 'text-accent' : 'text-primary hover:text-accent'
          }`}
          onClick={onNavigate}
        >
          {label}
        </Link>
        <span className="text-caption text-text-light">{pageRange}</span>
        {node.children.length > 0 && (
          <span className="text-caption text-text-light">{node.children.length} 個子節</span>
        )}
      </div>
      {node.children.length > 0 && (
        <div className="ml-4 mt-2 space-y-2 border-l border-border pl-4">
          {node.children.map((childId) => (
            <GuideOutlineTreeNode
              key={childId}
              subjectId={subjectId}
              nodeId={childId}
              nodesById={nodesById}
              activeId={activeId}
              variant={variant}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  )
}
