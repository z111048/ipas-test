import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import guideOutlinesRaw from '../../generated/guideOutlines.json'
import { galleryRoute, resourceLevels, type ResourceNavItem } from '../../data/resourceRegistry'
import type { GuideOutlinesData } from '../../types'
import GuideOutlineTree from '../guide/GuideOutlineTree'

const guideOutlines = guideOutlinesRaw as GuideOutlinesData

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

function badge(status?: ResourceNavItem['status']) {
  if (status === 'pending') return '待建立'
  if (status === 'external') return '官方連結'
  return null
}

function navItemClass(isActive: boolean, disabled = false) {
  if (disabled) {
    return 'block py-[0.55rem] px-5 text-[0.85rem] border-l-[3px] border-l-transparent text-white/45 cursor-not-allowed'
  }
  return `block py-[0.55rem] px-5 cursor-pointer text-[0.85rem] border-l-[3px] transition-all duration-150 no-underline ${
    isActive
      ? 'bg-white/10 border-l-accent text-white font-semibold'
      : 'border-l-transparent text-white/85 hover:bg-white/8 hover:text-white'
  }`
}

function ItemLabel({ item }: { item: ResourceNavItem }) {
  const itemBadge = badge(item.status)
  return (
    <span className="flex items-center justify-between gap-2">
      <span>{item.label}</span>
      {itemBadge && (
        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[0.68rem] text-white/75">
          {itemBadge}
        </span>
      )}
    </span>
  )
}

function SidebarItem({ item, onClose }: { item: ResourceNavItem; onClose: () => void }) {
  if (item.status === 'pending' || (!item.to && !item.externalUrl)) {
    return (
      <div className={navItemClass(false, true)} title={item.detail}>
        <ItemLabel item={item} />
      </div>
    )
  }

  if (item.externalUrl) {
    return (
      <a
        href={item.externalUrl}
        target="_blank"
        rel="noreferrer"
        className={navItemClass(false)}
        onClick={onClose}
        title={item.detail}
      >
        <ItemLabel item={item} />
      </a>
    )
  }

  return (
    <NavLink
      to={item.to!}
      end={item.to === '/'}
      className={({ isActive }) => navItemClass(isActive)}
      onClick={onClose}
      title={item.detail}
    >
      <ItemLabel item={item} />
    </NavLink>
  )
}

function Section({
  heading,
  children,
}: {
  heading: string
  children: ReactNode
}) {
  return (
    <div>
      <div className="h-px bg-white/10 mx-4 my-2" />
      <div className="py-2">
        <div className="text-[0.7rem] uppercase tracking-widest text-white/50 px-4 pt-2 pb-1 font-semibold">
          {heading}
        </div>
        {children}
      </div>
    </div>
  )
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <aside
      className={`
        fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[286px] bg-primary text-white
        overflow-y-auto flex-shrink-0 pb-8 z-50 transition-transform duration-300
        md:relative md:top-auto md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      <div className="py-2">
        <div className="text-[0.7rem] uppercase tracking-widest text-white/50 px-4 pt-2 pb-1 font-semibold">
          總覽
        </div>
        <SidebarItem item={{ label: '首頁', to: '/', status: 'available' }} onClose={onClose} />
      </div>

      {resourceLevels.map((level) => (
        <div key={level.id}>
          <Section heading={`${level.label}：科目與學習`}>
            {level.subjects.map((subject) => (
              <SidebarItem
                key={subject.id}
                item={{
                  label: `${subject.shortLabel}總覽`,
                  detail: `${subject.chapters} 個章節`,
                  to: subject.overviewTo,
                  status: 'available',
                }}
                onClose={onClose}
              />
            ))}
          </Section>

          <Section heading={`${level.label}：章節練習`}>
            {level.subjects.map((subject) => (
              <SidebarItem
                key={subject.id}
                item={{
                  label: subject.label,
                  detail: subject.practiceLabel,
                  to: subject.practiceTo,
                  status: subject.practiceStatus,
                }}
                onClose={onClose}
              />
            ))}
          </Section>

          {level.subjects.map((subject) => {
            const guide = guideOutlines.guides[subject.id]
            if (!guide) return null
            return (
              <Section key={subject.id} heading={`${level.label}學習指引 ${subject.shortLabel}`}>
                <GuideOutlineTree
                  subjectId={subject.id}
                  rootIds={guide.root}
                  nodesById={guide.nodesById}
                  variant="sidebar"
                  onNavigate={onClose}
                />
              </Section>
            )
          })}

          <Section heading={`${level.label}：公告試題與樣題`}>
            {[...level.exams, ...level.samples].map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
          </Section>

          <Section heading={`${level.label}：官方參考`}>
            {level.references.map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
            <SidebarItem
              item={{
                label: `${level.label}圖片與表格`,
                to: galleryRoute(level.label, 'guide1'),
                status: 'available',
              }}
              onClose={onClose}
            />
          </Section>
        </div>
      ))}
    </aside>
  )
}
