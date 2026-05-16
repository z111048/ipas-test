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
            `block py-[0.5rem] pr-4 cursor-pointer text-[0.82rem] border-l-[3px] transition-all duration-150 no-underline ${
              isActive || activeId === node.id
                ? 'bg-white/10 border-l-accent text-white font-semibold'
                : 'border-l-transparent text-white/85 hover:bg-white/8 hover:text-white'
            }`
          }
          style={{ paddingLeft: `${1 + (node.depth - 1) * 0.9}rem` }}
          onClick={onNavigate}
        >
          <span className="block truncate">📖 {label}</span>
          <span className="block text-[0.68rem] text-white/45 mt-0.5">{pageRange}</span>
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
          className={`text-[0.9rem] font-medium no-underline ${
            isActive ? 'text-accent' : 'text-primary hover:text-accent'
          }`}
        >
          {label}
        </Link>
        <span className="text-[0.72rem] text-text-light">{pageRange}</span>
        {node.children.length > 0 && (
          <span className="text-[0.72rem] text-text-light">{node.children.length} 個子節</span>
        )}
      </div>
      {node.children.length > 0 && (
        <div className="ml-5 mt-2 space-y-2 border-l border-border pl-4">
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
