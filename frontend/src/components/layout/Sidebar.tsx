import { memo, useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import guideOutlinesRaw from '../../generated/guideOutlines.json'
import { galleryRoute, resourceLevels, type ResourceNavItem } from '../../data/resourceRegistry'
import type { GuideOutlinesData } from '../../types'
import GuideOutlineTree from '../guide/GuideOutlineTree'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
const STORAGE_KEY = 'ipas-sidebar-expanded-v2'

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
    return 'block py-2 px-5 text-[0.84rem] border-l-[3px] border-l-transparent text-white/40 cursor-not-allowed'
  }
  return `block py-2 px-5 cursor-pointer text-[0.84rem] border-l-[3px] transition-all duration-150 no-underline ${
    isActive
      ? 'bg-white/12 border-l-accent text-white font-semibold'
      : 'border-l-transparent text-white/78 hover:bg-white/8 hover:text-white'
  }`
}

function ItemLabel({ item }: { item: ResourceNavItem }) {
  const itemBadge = badge(item.status)
  return (
    <span className="flex items-center justify-between gap-2">
      <span>{item.label}</span>
      {itemBadge && (
        <span className="rounded-full border border-white/10 bg-white/8 px-2 py-0.5 text-[0.66rem] text-white/70">
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

function loadExpandedState() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value ? JSON.parse(value) as Record<string, boolean> : {}
  } catch {
    return {}
  }
}

function Section({
  id,
  heading,
  tone = 'normal',
  open,
  onToggle,
  children,
}: {
  id: string
  heading: string
  tone?: 'level' | 'normal'
  open: boolean
  onToggle: (id: string) => void
  children: ReactNode
}) {
  const isOpen = open
  const buttonClass = tone === 'level'
    ? 'mx-3 mt-3 w-[calc(100%-1.5rem)] rounded-md border border-white/10 bg-white/10 px-3 py-2 text-left text-[0.86rem] font-semibold text-white hover:bg-white/14'
    : 'w-full px-4 pt-2 pb-1 text-left text-[0.68rem] uppercase tracking-widest text-white/50 font-semibold hover:text-white/75'

  const content = isOpen ? children : null
  if (tone === 'level') {
    return (
      <div className="mb-1">
        <button type="button" className={buttonClass} onClick={() => onToggle(id)} aria-expanded={isOpen}>
          <span className="inline-block w-4 text-white/70">{isOpen ? '▾' : '▸'}</span>
          {heading}
        </button>
        {content}
      </div>
    )
  }

  return (
    <div>
      <div className="h-px bg-white/10 mx-4 my-2" />
      <div className="py-2">
        <button type="button" className={buttonClass} onClick={() => onToggle(id)} aria-expanded={isOpen}>
          <span className="inline-block w-4 text-white/45">{isOpen ? '▾' : '▸'}</span>
          {heading}
        </button>
        {content}
      </div>
    </div>
  )
}

function Sidebar({ isOpen, onClose }: SidebarProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => loadExpandedState())

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(expanded))
  }, [expanded])

  const defaults = useMemo(() => ({
    overview: true,
    'level-junior': true,
    'level-middle': true,
  }), [])

  const toggle = (id: string) => {
    setExpanded((current) => ({
      ...current,
      [id]: !(current[id] ?? Boolean(defaults[id as keyof typeof defaults])),
    }))
  }

  const isSectionOpen = (id: string) => expanded[id] ?? Boolean(defaults[id as keyof typeof defaults])

  return (
    <aside
      className={`
        fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[292px] bg-[#132b43] text-white
        flex-shrink-0 z-50 transition-transform duration-300
        md:sticky md:top-0 md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      <div className="h-full overflow-y-auto overflow-x-hidden pb-8 scrollbar-hidden border-r border-slate-950/20">
      <Section
        id="overview"
        heading="總覽"
        open={isSectionOpen('overview')}
        onToggle={toggle}
      >
        <SidebarItem item={{ label: '首頁', to: '/', status: 'available' }} onClose={onClose} />
      </Section>

      {resourceLevels.map((level) => {
        const levelId = `level-${level.id}`
        const subjectItems = level.subjects.map((subject) => ({
          label: `${subject.shortLabel}總覽`,
          detail: `${subject.chapters} 個章節`,
          to: subject.overviewTo,
          status: 'available' as const,
        }))
        const practiceItems = level.subjects.map((subject) => ({
          label: `${subject.shortLabel}AI 舊版練習`,
          detail: subject.practiceDetail,
          to: subject.practiceTo,
          status: subject.practiceStatus,
        }))
        const guideExerciseItems = level.subjects.flatMap((subject) => {
          if (!subject.guideExercisePracticeTo) return []
          return [{
            label: `${subject.shortLabel}學習指引練習`,
            detail: subject.guideExercisePracticeDetail,
            to: subject.guideExercisePracticeTo,
            status: 'available' as const,
          }]
        })
        const codex100Items = level.subjects.flatMap((subject) => {
          if (!subject.codex100PracticeTo) return []
          return [{
            label: `${subject.shortLabel}Codex 100 題`,
            detail: subject.codex100PracticeDetail,
            to: subject.codex100PracticeTo,
            status: 'available' as const,
          }]
        })
        const examItems = [...level.exams, ...level.samples]
        const referenceItems = [
          ...level.references,
          {
            label: `${level.label}圖片與表格`,
            to: galleryRoute(level.label, 'guide1'),
            status: 'available' as const,
          },
        ]
        return (
        <div key={level.id}>
          <Section
            id={levelId}
            heading={`${level.label}資源`}
            tone="level"
            open={isSectionOpen(levelId)}
            onToggle={toggle}
          >
            <div className="px-4 pt-2 pb-1 text-[0.74rem] leading-5 text-white/60">
              {level.subtitle}
            </div>
          </Section>

          {isSectionOpen(levelId) && (
          <>
          <Section
            id={`${level.id}-subjects`}
            heading="科目總覽"
            open={isSectionOpen(`${level.id}-subjects`)}
            onToggle={toggle}
          >
            {subjectItems.map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
          </Section>

          <Section
            id={`${level.id}-practice`}
            heading="AI 章節練習（舊版）"
            open={isSectionOpen(`${level.id}-practice`)}
            onToggle={toggle}
          >
            {practiceItems.map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
          </Section>

          {guideExerciseItems.length > 0 && (
            <Section
              id={`${level.id}-guide-exercise-practice`}
              heading="學習指引練習"
              open={isSectionOpen(`${level.id}-guide-exercise-practice`)}
              onToggle={toggle}
            >
              {guideExerciseItems.map((item) => (
                <SidebarItem key={item.label} item={item} onClose={onClose} />
              ))}
            </Section>
          )}

          {codex100Items.length > 0 && (
            <Section
              id={`${level.id}-codex100-practice`}
              heading="Codex 100 題"
              open={isSectionOpen(`${level.id}-codex100-practice`)}
              onToggle={toggle}
            >
              {codex100Items.map((item) => (
                <SidebarItem key={item.label} item={item} onClose={onClose} />
              ))}
            </Section>
          )}

          {level.subjects.map((subject) => {
            const guide = guideOutlines.guides[subject.id]
            if (!guide) return null
            const sectionId = `${level.id}-guide-${subject.id}`
            return (
              <Section
                key={subject.id}
                id={sectionId}
                heading={`學習指引 ${subject.shortLabel}`}
                open={isSectionOpen(sectionId)}
                onToggle={toggle}
              >
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

          <Section
            id={`${level.id}-exams`}
            heading="公告試題與樣題"
            open={isSectionOpen(`${level.id}-exams`)}
            onToggle={toggle}
          >
            {examItems.map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
          </Section>

          <Section
            id={`${level.id}-references`}
            heading="官方參考"
            open={isSectionOpen(`${level.id}-references`)}
            onToggle={toggle}
          >
            {referenceItems.map((item) => (
              <SidebarItem key={item.label} item={item} onClose={onClose} />
            ))}
          </Section>
          </>
          )}
        </div>
        )
      })}
      </div>
    </aside>
  )
}

export default memo(Sidebar)
