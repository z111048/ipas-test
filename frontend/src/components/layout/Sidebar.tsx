import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { galleryRoute, resourceLevels, type ResourceNavItem, type SubjectResource } from '../../data/resourceRegistry'
import { guideNav } from '../../data/guideNav'

const STORAGE_KEY = 'ipas-sidebar-expanded-v4'

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

/** 學習指引底下的章／節。資料來自 guideNav.json（13 KB，只有章節兩層）。 */
function GuideNavNodes({
  subjectId,
  nodeIds,
  onClose,
}: {
  subjectId: string
  nodeIds: string[]
  onClose: () => void
}) {
  const guide = guideNav.guides[subjectId]
  if (!guide) return null

  return (
    <>
      {nodeIds.map((nodeId) => {
        const node = guide.nodesById[nodeId]
        if (!node?.route) return null
        // 節（toc 的章）縮排一級；前置章沒有子節點，維持在章的層級
        const indent = node.depth === 1 ? '1.75rem' : '2.6rem'
        return (
          <div key={nodeId}>
            <NavLink
              to={node.route}
              className={({ isActive }) =>
                `block py-1 pr-3 text-[0.78rem] leading-5 border-l-[3px] transition-all duration-150 no-underline ${
                  isActive
                    ? 'bg-white/12 border-l-accent text-white font-semibold'
                    : 'border-l-transparent text-white/62 hover:bg-white/8 hover:text-white'
                }`
              }
              style={{ paddingLeft: indent }}
              onClick={onClose}
            >
              <span className="block truncate">{node.title}</span>
            </NavLink>
            {node.childIds.length > 0 && (
              <GuideNavNodes subjectId={subjectId} nodeIds={node.childIds} onClose={onClose} />
            )}
          </div>
        )
      })}
    </>
  )
}

function SubjectBlock({
  subject,
  onClose,
  guideOpen,
  onToggleGuide,
}: {
  subject: SubjectResource
  onClose: () => void
  guideOpen: boolean
  onToggleGuide: () => void
}) {
  const colonIdx = subject.label.indexOf('：')
  const subjectNum = colonIdx > -1 ? subject.label.slice(0, colonIdx) : subject.label
  const subjectName = colonIdx > -1 ? subject.label.slice(colonIdx + 1) : ''
  const navGuide = guideNav.guides[subject.id]

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

      {/* 學習指引（可展開到章／節） */}
      {subject.guideTo && (
        <div>
          <div className="flex items-stretch">
            <NavLink
              to={subject.guideTo}
              className={({ isActive }) => `${navItemClass(isActive)} flex-1 min-w-0 truncate`}
              onClick={onClose}
            >
              學習指引
            </NavLink>
            {navGuide && navGuide.rootIds.length > 0 && (
              <button
                type="button"
                className="px-2.5 text-white/45 hover:text-white text-[0.7rem]"
                onClick={onToggleGuide}
                aria-expanded={guideOpen}
                aria-label={guideOpen ? '收合章節' : '展開章節'}
              >
                {guideOpen ? '▾' : '▸'}
              </button>
            )}
          </div>
          {guideOpen && navGuide && (
            <GuideNavNodes subjectId={subject.id} nodeIds={navGuide.rootIds} onClose={onClose} />
          )}
        </div>
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
  const location = useLocation()
  const navRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(expanded))
  }, [expanded])

  // 進入某科目相關頁面（科目總覽／章節練習／學習指引）時，自動展開該科目所屬的級別區塊
  const activeSubjectId = useMemo(() => {
    const match = location.pathname.match(/^\/(?:subject|practice|guide)\/([^/]+)/)
    return match?.[1]
  }, [location.pathname])

  useEffect(() => {
    if (!activeSubjectId) return
    const level = resourceLevels.find((lvl) => lvl.subjects.some((s) => s.id === activeSubjectId))
    if (!level) return
    const levelId = `level-${level.id}`
    const guideId = `guide-${activeSubjectId}`
    const onGuidePage = location.pathname.startsWith('/guide/')
    setExpanded((current) => {
      const next = { ...current }
      let changed = false
      if (!next[levelId]) { next[levelId] = true; changed = true }
      if (onGuidePage && !next[guideId]) { next[guideId] = true; changed = true }
      return changed ? next : current
    })
  }, [activeSubjectId, location.pathname])

  // 展開狀態或路由變化後，將目前作用中的連結捲動到可視範圍內
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const activeEl = navRef.current?.querySelector('[aria-current="page"]')
      activeEl?.scrollIntoView({ block: 'nearest' })
    })
    return () => cancelAnimationFrame(frame)
  }, [location.pathname, expanded])

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
      <div ref={navRef} className="h-full overflow-y-auto overflow-x-hidden pb-8 overscroll-contain scrollbar-sidebar border-r border-slate-950/20">
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
          <NavLink
            to="/visuals"
            className={({ isActive }) => navItemClass(isActive)}
            onClick={onClose}
          >
            概念圖卡
          </NavLink>
          <NavLink
            to="/outline"
            className={({ isActive }) => navItemClass(isActive)}
            onClick={onClose}
          >
            完整目錄
          </NavLink>
          <NavLink
            to="/mindmap"
            className={({ isActive }) => navItemClass(isActive)}
            onClick={onClose}
          >
            考點熱度圖
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
                    <SubjectBlock
                      key={subject.id}
                      subject={subject}
                      onClose={onClose}
                      guideOpen={isOpen_(`guide-${subject.id}`)}
                      onToggleGuide={() => toggle(`guide-${subject.id}`)}
                    />
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
