import { NavLink } from 'react-router-dom'
import tocRaw from '@data/toc_manifest.json'
import guideOutlinesRaw from '../../generated/guideOutlines.json'
import type { GuideOutlinesData, TocManifest } from '../../types'
import GuideOutlineTree from '../guide/GuideOutlineTree'

interface NavItem {
  label: string
  to: string
}

interface NavSection {
  heading: string
  items: NavItem[]
}

interface GuideNavSection {
  heading: string
  subjectId: string
}

const toc = tocRaw as TocManifest
const guideOutlines = guideOutlinesRaw as GuideOutlinesData

function examKeyForSubject(subjectId: string) {
  const match = subjectId.match(/^s(\d+)$/)
  return match ? `mock${match[1]}` : undefined
}

const NAV_SECTIONS: NavSection[] = [
  {
    heading: '總覽',
    items: [{ label: '🏠 首頁', to: '/' }],
  },
  ...toc.subjects.map((subject) => {
    const examKey = examKeyForSubject(subject.id)
    return {
      heading: subject.subject,
      items: [
        { label: '📖 章節總覽', to: `/subject/${subject.id}` },
        ...subject.chapters.map((chapter) => ({
          label: `✏️ ${chapter.title}`,
          to: `/practice/${subject.id}/${chapter.id}`,
        })),
        ...(examKey ? [{ label: `🎯 模擬考試（${subject.subject.split('：')[0]}）`, to: `/exam/${examKey}` }] : []),
      ],
    }
  }),
  {
    heading: '樣題練習',
    items: [{ label: '📝 考試樣題（114年9月版）', to: '/exam/sample' }],
  },
  {
    heading: 'PDF 資源',
    items: [{ label: '🖼️ 圖片與表格', to: '/images' }],
  },
]

const GUIDE_NAV_SECTIONS: GuideNavSection[] = toc.subjects.map((subject) => ({
    heading: `學習指引 ${subject.subject.split('：')[0]}`,
    subjectId: subject.id,
  }))

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const itemClass = ({ isActive }: { isActive: boolean }) =>
    `block py-[0.55rem] px-5 cursor-pointer text-[0.85rem] border-l-[3px] transition-all duration-150 no-underline ${
      isActive
        ? 'bg-white/10 border-l-accent text-white font-semibold'
        : 'border-l-transparent text-white/85 hover:bg-white/8 hover:text-white'
    }`

  return (
    <aside
      className={`
        fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[260px] bg-primary text-white
        overflow-y-auto flex-shrink-0 pb-8 z-50 transition-transform duration-300
        md:relative md:top-auto md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      {NAV_SECTIONS.map((section, si) => (
        <div key={si}>
          {si > 0 && <div className="h-px bg-white/10 mx-4 my-2" />}
          <div className="py-2">
            <div className="text-[0.7rem] uppercase tracking-widest text-white/50 px-4 pt-2 pb-1 font-semibold">
              {section.heading}
            </div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={itemClass}
                onClick={onClose}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
      {GUIDE_NAV_SECTIONS.map((section) => {
        const guide = guideOutlines.guides[section.subjectId]
        if (!guide) return null
        return (
          <div key={section.subjectId}>
            <div className="h-px bg-white/10 mx-4 my-2" />
            <div className="py-2">
              <div className="text-[0.7rem] uppercase tracking-widest text-white/50 px-4 pt-2 pb-1 font-semibold">
                {section.heading}
              </div>
              <GuideOutlineTree
                subjectId={section.subjectId}
                rootIds={guide.root}
                nodesById={guide.nodesById}
                variant="sidebar"
                onNavigate={onClose}
              />
            </div>
          </div>
        )
      })}
    </aside>
  )
}
