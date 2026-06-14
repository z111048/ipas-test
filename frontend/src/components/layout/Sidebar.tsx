import { memo, useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { galleryRoute, resourceLevels, type ResourceNavItem, type SubjectResource } from '../../data/resourceRegistry'

const STORAGE_KEY = 'ipas-sidebar-expanded-v3'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

function navItemClass(isActive: boolean, disabled = false) {
  if (disabled) {
    return 'block py-1.5 px-5 text-[0.83rem] border-l-[3px] border-l-transparent text-white/35 cursor-not-allowed'
  }
  return `block py-1.5 px-5 cursor-pointer text-[0.83rem] border-l-[3px] transition-all duration-150 no-underline ${
    isActive
      ? 'bg-white/12 border-l-accent text-white font-semibold'
      : 'border-l-transparent text-white/72 hover:bg-white/8 hover:text-white'
  }`
}

function SidebarLink({
  item,
  onClose,
}: {
  item: ResourceNavItem
  onClose: () => void
}) {
  if (!item.to && !item.externalUrl) {
    return (
      <span className={navItemClass(false, true)} title={item.detail}>
        {item.label}
        {item.status === 'pending' && (
          <span className="ml-2 text-[0.65rem] text-white/40">待建立</span>
        )}
      </span>
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
        {item.label}
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
      {item.label}
    </NavLink>
  )
}

function SubjectBlock({
  subject,
  onClose,
}: {
  subject: SubjectResource
  onClose: () => void
}) {
  const colonIdx = subject.label.indexOf('：')
  const subjectNum = colonIdx > -1 ? subject.label.slice(0, colonIdx) : subject.label
  const subjectName = colonIdx > -1 ? subject.label.slice(colonIdx + 1) : ''

  return (
    <div className="mb-0.5">
      {/* Subject label */}
      <div className="flex items-center gap-2 pl-4 pr-3 pt-2.5 pb-0.5">
        <div className="w-0.5 h-3.5 rounded-full bg-accent/70 shrink-0" />
        <span className="text-[0.78rem] font-semibold text-white/90">{subjectNum}</span>
        {subjectName && (
          <span className="text-[0.66rem] text-white/38 truncate">{subjectName}</span>
        )}
      </div>

      {/* 學習指引 */}
      {subject.guideTo && (
        <NavLink
          to={subject.guideTo}
          className={({ isActive }) => navItemClass(isActive)}
          onClick={onClose}
        >
          學習指引
        </NavLink>
      )}

      <NavLink
        to={`/articles?subject=${subject.id}`}
        className={() => navItemClass(false)}
        onClick={onClose}
      >
        主題文章
      </NavLink>

      {/* 練習 */}
      {subject.practiceTo && (
        <SidebarLink
          item={{ label: '章節練習', to: subject.practiceTo, status: subject.practiceStatus, detail: subject.practiceDetail }}
          onClose={onClose}
        />
      )}
      {subject.guideExercisePracticeTo && (
        <SidebarLink
          item={{ label: '指引練習', to: subject.guideExercisePracticeTo, status: 'available', detail: subject.guideExercisePracticeDetail }}
          onClose={onClose}
        />
      )}
      {subject.codex100PracticeTo && (
        <SidebarLink
          item={{ label: 'Codex 100 題', to: subject.codex100PracticeTo, status: 'available', detail: subject.codex100PracticeDetail }}
          onClose={onClose}
        />
      )}

      {/* 科目總覽 */}
      <NavLink
        to={subject.overviewTo!}
        className={({ isActive }) => navItemClass(isActive)}
        onClick={onClose}
      >
        科目總覽
      </NavLink>
    </div>
  )
}

function CollapsibleSection({
  id,
  heading,
  open,
  onToggle,
  children,
}: {
  id: string
  heading: string
  open: boolean
  onToggle: (id: string) => void
  children: React.ReactNode
}) {
  return (
    <div className="mt-1">
      <button
        type="button"
        className="w-full px-4 pt-1.5 pb-0.5 text-left text-[0.67rem] uppercase tracking-widest text-white/42 font-semibold hover:text-white/65 flex items-center gap-1"
        onClick={() => onToggle(id)}
        aria-expanded={open}
      >
        <span className="inline-block w-3 text-white/35">{open ? '▾' : '▸'}</span>
        {heading}
      </button>
      {open && <div>{children}</div>}
    </div>
  )
}

function loadExpandedState() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value ? (JSON.parse(value) as Record<string, boolean>) : {}
  } catch {
    return {}
  }
}

function Sidebar({ isOpen, onClose }: SidebarProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => loadExpandedState())

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(expanded))
  }, [expanded])

  const defaults = useMemo(
    () => ({
      'level-junior': true,
      'level-middle': false,
      'junior-exams': false,
      'junior-references': false,
      'middle-exams': false,
      'middle-references': false,
    }),
    [],
  )

  const toggle = (id: string) => {
    setExpanded((current) => ({
      ...current,
      [id]: !(current[id] ?? Boolean(defaults[id as keyof typeof defaults])),
    }))
  }

  const isOpen_ = (id: string) =>
    expanded[id] ?? Boolean(defaults[id as keyof typeof defaults])

  return (
    <aside
      className={`
        fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[272px] bg-[#132b43] text-white
        flex-shrink-0 z-50 transition-transform duration-300
        md:sticky md:top-0 md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      <div className="h-full overflow-y-auto overflow-x-hidden pb-8 overscroll-contain scrollbar-sidebar border-r border-slate-950/20">
        {/* 首頁 */}
        <div className="pt-2 pb-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) => navItemClass(isActive)}
            onClick={onClose}
          >
            首頁
          </NavLink>
          <NavLink
            to="/articles"
            className={({ isActive }) => navItemClass(isActive)}
            onClick={onClose}
          >
            主題文章
          </NavLink>
        </div>

        {resourceLevels.map((level) => {
          const levelId = `level-${level.id}`
          const isLevelOpen = isOpen_(levelId)
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
              {/* Divider */}
              <div className="h-px bg-white/10 mx-4 my-2" />

              {/* Level toggle */}
              <button
                type="button"
                className="mx-3 w-[calc(100%-1.5rem)] rounded-md border border-white/10 bg-white/10 px-3 py-2 text-left text-[0.86rem] font-semibold text-white hover:bg-white/14 flex items-center gap-1.5"
                onClick={() => toggle(levelId)}
                aria-expanded={isLevelOpen}
              >
                <span className="text-white/60 w-3.5">{isLevelOpen ? '▾' : '▸'}</span>
                {level.label}
                <span className="ml-auto text-[0.68rem] font-normal text-white/38">
                  {level.subjects.length} 科目
                </span>
              </button>

              {isLevelOpen && (
                <div className="mt-1">
                  {/* Per-subject blocks */}
                  {level.subjects.map((subject) => (
                    <SubjectBlock key={subject.id} subject={subject} onClose={onClose} />
                  ))}

                  {/* 試題庫 */}
                  <div className="mx-4 mt-3 mb-1 h-px bg-white/8" />
                  <CollapsibleSection
                    id={`${level.id}-exams`}
                    heading="試題庫"
                    open={isOpen_(`${level.id}-exams`)}
                    onToggle={toggle}
                  >
                    {examItems.map((item) => (
                      <SidebarLink key={item.label} item={item} onClose={onClose} />
                    ))}
                  </CollapsibleSection>

                  {/* 官方資料 */}
                  <CollapsibleSection
                    id={`${level.id}-references`}
                    heading="官方資料"
                    open={isOpen_(`${level.id}-references`)}
                    onToggle={toggle}
                  >
                    {referenceItems.map((item) => (
                      <SidebarLink key={item.label} item={item} onClose={onClose} />
                    ))}
                  </CollapsibleSection>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}

export default memo(Sidebar)
