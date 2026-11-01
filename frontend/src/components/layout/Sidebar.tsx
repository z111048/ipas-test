import { memo, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { resourceLevels, type LevelResource, type ResourceNavItem, type SubjectResource } from '../../data/resourceRegistry'
import { examByRouteKey, type ResourceLevelId } from '../../data/resourceCatalog'
import { guideNav } from '../../data/guideNav'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import { useLearningIndex } from '../../features/learning/useLearningIndex'
import { LevelPicker } from '../ui'
import SearchIcon from './SearchIcon'
import {
  NAV_GROUP_LABELS,
  SEARCH_LABEL,
  SECTION_LABELS,
  formatSubjectLabel,
  navLabel,
} from '../../constants/navLabels'

/**
 * 主選單。分四組：學習／練習／公告試題／工具。
 *
 * 級別（初級／中級）由目前路由推得（科目頁、練習、學習指引、公告試題），其他頁面沿用
 * 使用者上次在選單選的級別。科目、試題清單一律由 resourceLevels（toc_manifest +
 * resource_catalog）推得，不在此硬編（CLAUDE.md 不變量 1）。
 */

const LEVEL_STORAGE_KEY = 'ipas-sidebar-level-v1'
const REFERENCES_STORAGE_KEY = 'ipas-sidebar-references-v1'

interface SidebarProps {
  id: string
  isOpen: boolean
  onClose: () => void
  /** Opens the site search (mobile drawer header). */
  onSearch: () => void
  restoreFocusRef?: RefObject<HTMLElement | null>
  /** Focus mode: hide the sidebar entirely (desktop column collapses). */
  collapsed?: boolean
}

const ROW_BASE = 'flex min-h-[max(2.5rem,var(--control-min-h))] items-center gap-2 py-2 pr-3 text-meta leading-5 border-l-[3px] transition-all duration-150 no-underline'

function navItemClass(isActive: boolean, disabled = false, indent = 'pl-5') {
  if (disabled) {
    return `${ROW_BASE} ${indent} border-l-transparent text-on-dark-muted cursor-not-allowed`
  }
  return `${ROW_BASE} ${indent} cursor-pointer ${
    isActive
      ? 'bg-white/12 border-l-accent text-on-dark font-semibold'
      : 'border-l-transparent text-on-dark-muted hover:bg-white/8 hover:text-on-dark'
  }`
}

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // storage unavailable (private mode) — preference just isn't remembered
  }
}

function SidebarLink({
  item,
  onClose,
  indent,
}: {
  item: ResourceNavItem
  onClose: () => void
  indent?: string
}) {
  if (!item.to && !item.externalUrl) {
    return (
      <span className={navItemClass(false, true, indent)} title={item.detail}>
        {item.label}
        {item.status === 'pending' && (
          <span className="ml-auto rounded border border-white/25 px-1.5 text-caption text-on-dark-muted">待建立</span>
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
        className={navItemClass(false, false, indent)}
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
      className={({ isActive }) => navItemClass(isActive, false, indent)}
      onClick={onClose}
      title={item.detail}
    >
      {item.label}
    </NavLink>
  )
}

function GroupHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="m-0 px-4 pt-3 pb-1 text-caption font-semibold tracking-wider text-on-dark-muted">
      {children}
    </h2>
  )
}

function SubHeading({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 px-5 pt-1.5 pb-0.5 text-caption text-on-dark-muted">{children}</p>
  )
}

function NavGroup({ label, suffix, children }: { label: string; suffix?: string; children: ReactNode }) {
  return (
    <section className="pb-1">
      <div className="mx-4 mt-2 h-px bg-white/10" />
      <GroupHeading>
        {label}
        {suffix && <span className="font-normal">・{suffix}</span>}
      </GroupHeading>
      {children}
    </section>
  )
}

/** 學習指引底下的章／節。資料來自 guideNav.json（只有章節兩層）。 */
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
        const indent = node.depth === 1 ? 'pl-[2.25rem]' : 'pl-[3rem]'
        return (
          <div key={nodeId}>
            <NavLink
              to={node.route}
              className={({ isActive }) => navItemClass(isActive, false, indent)}
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

/** 一個科目：標題列可展開，展開後是科目總覽與學習指引的章／節。 */
function SubjectTree({
  subject,
  levelLabel,
  open,
  onToggle,
  onClose,
}: {
  subject: SubjectResource
  levelLabel: string
  open: boolean
  onToggle: () => void
  onClose: () => void
}) {
  const { number, name, full } = formatSubjectLabel(levelLabel, subject.label)
  const navGuide = guideNav.guides[subject.id]
  const panelId = `sidebar-subject-${subject.id}`

  return (
    <div>
      <button
        type="button"
        className="flex min-h-[max(2.5rem,var(--control-min-h))] w-full items-center gap-2 border-l-[3px] border-l-transparent py-2 pl-[1.1rem] pr-3 text-left text-meta text-on-dark hover:bg-white/8"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        title={full}
      >
        <span className="inline-block w-3 shrink-0 text-on-dark-muted" aria-hidden="true">{open ? '▾' : '▸'}</span>
        <span className="shrink-0 font-semibold">{number}</span>
        {name && <span className="min-w-0 truncate text-caption text-on-dark-muted">{name}</span>}
      </button>
      {open && (
        <div id={panelId}>
          {subject.overviewTo && (
            <NavLink
              to={subject.overviewTo}
              className={({ isActive }) => navItemClass(isActive, false, 'pl-[2.25rem]')}
              onClick={onClose}
            >
              {navLabel('subject')}
            </NavLink>
          )}
          {navGuide && navGuide.rootIds.length > 0 ? (
            <GuideNavNodes subjectId={subject.id} nodeIds={navGuide.rootIds} onClose={onClose} />
          ) : (
            subject.guideTo && (
              <NavLink
                to={subject.guideTo}
                className={({ isActive }) => navItemClass(isActive, false, 'pl-[2.25rem]')}
                onClick={onClose}
              >
                {navLabel('guide')}
              </NavLink>
            )
          )}
        </div>
      )}
    </div>
  )
}

/** 章節練習／學習指引練習：以路由前綴判斷作用中（不只第一章）。 */
function PracticeLink({
  to,
  label,
  subjectNumber,
  active,
  disabled,
  detail,
  onClose,
}: {
  to?: string
  label: string
  subjectNumber: string
  active: boolean
  disabled?: boolean
  detail?: string
  onClose: () => void
}) {
  const content = (
    <>
      <span>{label}</span>
      <span className="ml-auto shrink-0 text-caption font-normal text-on-dark-muted">{subjectNumber}</span>
    </>
  )
  if (!to || disabled) {
    return (
      <span className={navItemClass(false, true)} title={detail}>
        {content}
      </span>
    )
  }
  return (
    <Link
      to={to}
      className={navItemClass(active)}
      aria-current={active ? 'page' : undefined}
      onClick={onClose}
      title={detail}
    >
      {content}
    </Link>
  )
}

function useIsMobileSidebar() {
  const [isMobile, setIsMobile] = useState(() => (
    typeof window !== 'undefined'
      ? window.matchMedia('(max-width: 767px)').matches
      : false
  ))

  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)')
    const update = () => setIsMobile(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return isMobile
}

/** 從路由推得目前所在的科目與級別。 */
function routeContext(pathname: string): { subjectId?: string; levelId?: ResourceLevelId; examPath?: string } {
  const subjectMatch = pathname.match(/^\/(?:subject|practice|guide)\/([^/]+)/)
  if (subjectMatch) {
    const subjectId = decodeURIComponent(subjectMatch[1])
    const level = resourceLevels.find((lvl) => lvl.subjects.some((s) => s.id === subjectId))
    return { subjectId, levelId: level?.id }
  }
  const examMatch = pathname.match(/^\/exam\/([^/]+)/)
  if (examMatch) {
    const exam = examByRouteKey(decodeURIComponent(examMatch[1]))
    if (exam) return { subjectId: exam.subjectId ?? undefined, levelId: exam.levelId }
  }
  return {}
}

function isLevelId(value: string | null): value is ResourceLevelId {
  return Boolean(value && resourceLevels.some((level) => level.id === value))
}

function Sidebar({ id, isOpen, onClose, onSearch, restoreFocusRef, collapsed = false }: SidebarProps) {
  const location = useLocation()
  const navRef = useRef<HTMLDivElement>(null)
  const asideRef = useRef<HTMLElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const navigatingRef = useRef(false)
  const isMobile = useIsMobileSidebar()
  const modalActive = isOpen && isMobile && !collapsed
  const hiddenMobileDrawer = isMobile && !isOpen
  const { index: learningIndex } = useLearningIndex()

  const route = useMemo(() => routeContext(location.pathname), [location.pathname])

  // 使用者在選單切換的級別；路由本身屬於某級別時以路由為準
  const [preferredLevel, setPreferredLevel] = useState<ResourceLevelId>(() => {
    const stored = readStorage(LEVEL_STORAGE_KEY)
    return isLevelId(stored) ? stored : resourceLevels[0].id
  })
  useEffect(() => {
    if (route.levelId) setPreferredLevel(route.levelId)
  }, [route.levelId])
  const level: LevelResource = resourceLevels.find((lvl) => lvl.id === preferredLevel) ?? resourceLevels[0]
  const chooseLevel = (value: string) => {
    if (!isLevelId(value)) return
    setPreferredLevel(value)
    writeStorage(LEVEL_STORAGE_KEY, value)
  }

  // 科目樹：只展開目前路由所屬的科目；換到別的科目時重設
  const [openSubjects, setOpenSubjects] = useState<ReadonlySet<string>>(
    () => new Set(route.subjectId ? [route.subjectId] : []),
  )
  useEffect(() => {
    setOpenSubjects(new Set(route.subjectId ? [route.subjectId] : []))
  }, [route.subjectId])
  const toggleSubject = (subjectId: string) => {
    setOpenSubjects((current) => {
      const next = new Set(current)
      if (next.has(subjectId)) next.delete(subjectId)
      else next.add(subjectId)
      return next
    })
  }

  const [referencesOpen, setReferencesOpen] = useState(() => readStorage(REFERENCES_STORAGE_KEY) === '1')
  const toggleReferences = () => {
    setReferencesOpen((open) => {
      writeStorage(REFERENCES_STORAGE_KEY, open ? '0' : '1')
      return !open
    })
  }

  useEffect(() => {
    if (modalActive) navigatingRef.current = false
  }, [modalActive])

  useFocusTrap({
    active: modalActive,
    containerRef: asideRef,
    initialFocusRef: closeButtonRef,
    restoreFocusRef,
    onDismiss: onClose,
    lockBodyScroll: true,
    // 點連結導頁而關閉時，焦點交給 <main>（AppShell 會處理），不要跳回選單按鈕
    shouldRestoreFocus: () => !navigatingRef.current,
  })

  // 路由或展開狀態變化後，將目前作用中的連結捲動到可視範圍內
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const activeEl = navRef.current?.querySelector('[aria-current="page"]')
      activeEl?.scrollIntoView({ block: 'nearest' })
    })
    return () => cancelAnimationFrame(frame)
  }, [location.pathname, openSubjects, level.id])

  const pathname = location.pathname
  const toolRoutes = new Set(['/outline', '/mindmap', '/concepts', '/glossary', '/images'])
  // 官方資料（PDF 等）；已列在「工具」的站內頁面不重複
  const referenceItems = level.references.filter((item) => !item.to || !toolRoutes.has(item.to.split('?')[0]))
  const examItems = [...level.exams, ...level.samples]
  const hasGuidePractice = level.subjects.some((subject) => subject.guideExercisePracticeTo)

  return (
    <aside
      id={id}
      ref={asideRef}
      role={modalActive ? 'dialog' : 'navigation'}
      aria-modal={modalActive ? 'true' : undefined}
      aria-hidden={hiddenMobileDrawer ? 'true' : undefined}
      aria-label="主選單"
      inert={hiddenMobileDrawer || collapsed ? true : undefined}
      tabIndex={-1}
      onClickCapture={(event) => {
        const anchor = (event.target as HTMLElement).closest('a[href]')
        if (anchor && anchor.getAttribute('target') !== '_blank') navigatingRef.current = true
      }}
      className={`
        sidebar-drawer fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[272px] bg-sidebar text-on-dark
        flex-col flex-shrink-0 z-50 transition-transform duration-300
        md:sticky md:top-0 md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${collapsed ? 'hidden' : 'flex'}
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      {/* 手機抽屜頂列：搜尋與關閉 */}
      <div className="flex shrink-0 items-center gap-2 border-b border-white/10 px-3 py-2 md:hidden">
        <button
          type="button"
          className="touch-target inline-flex flex-1 items-center gap-2 rounded-md border border-white/20 bg-white/8 px-3 text-left text-ui text-on-dark hover:bg-white/14"
          onClick={onSearch}
        >
          <SearchIcon />
          <span>{SEARCH_LABEL}</span>
        </button>
        <button
          ref={closeButtonRef}
          type="button"
          className="touch-target inline-flex shrink-0 items-center justify-center rounded-md border border-white/20 bg-white/8 text-lg text-on-dark hover:bg-white/14"
          onClick={onClose}
          aria-label="關閉選單"
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>

      <div ref={navRef} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-8 overscroll-contain scrollbar-sidebar border-r border-slate-950/20">
        <div className="pt-2">
          <NavLink to="/" end className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('home')}
          </NavLink>
          {resourceLevels.length > 1 && (
            <LevelPicker
              label="選單顯示的級別"
              labelHidden
              value={level.id}
              onChange={chooseLevel}
              className="px-4 pt-2 pb-1"
            />
          )}
        </div>

        {/* 學習 */}
        <NavGroup label={NAV_GROUP_LABELS.learn}>
          <SubHeading>{level.label}{navLabel('guide')}</SubHeading>
          {level.subjects.map((subject) => (
            <SubjectTree
              key={subject.id}
              subject={subject}
              levelLabel={level.label}
              open={openSubjects.has(subject.id)}
              onToggle={() => toggleSubject(subject.id)}
              onClose={onClose}
            />
          ))}
          <NavLink to="/articles" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('articles')}
          </NavLink>
          <NavLink to="/visuals" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('visuals')}
          </NavLink>
          {learningIndex && (
            <>
              <NavLink to="/learn" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
                {navLabel('learn')}
              </NavLink>
              {learningIndex.projects.length > 0 && (
                <NavLink to="/projects" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
                  {navLabel('projects')}
                </NavLink>
              )}
            </>
          )}
        </NavGroup>

        {/* 練習 */}
        <NavGroup label={NAV_GROUP_LABELS.practice}>
          {level.subjects.map((subject) => {
            const { number } = formatSubjectLabel(level.label, subject.label)
            const inPractice = pathname.startsWith(`/practice/${subject.id}/`)
            const onGuidePractice = inPractice && /\/guide\/?$/.test(pathname)
            return (
              <PracticeLink
                key={subject.id}
                to={subject.practiceTo}
                label={navLabel('practice')}
                subjectNumber={number}
                active={inPractice && !onGuidePractice}
                disabled={subject.practiceStatus !== 'available'}
                detail={subject.practiceDetail}
                onClose={onClose}
              />
            )
          })}
          {hasGuidePractice && level.subjects.map((subject) => {
            if (!subject.guideExercisePracticeTo) return null
            const { number } = formatSubjectLabel(level.label, subject.label)
            const active = pathname.startsWith(`/practice/${subject.id}/`) && /\/guide\/?$/.test(pathname)
            return (
              <PracticeLink
                key={`${subject.id}-guide`}
                to={subject.guideExercisePracticeTo}
                label={navLabel('guidePractice')}
                subjectNumber={number}
                active={active}
                detail={subject.guideExercisePracticeDetail}
                onClose={onClose}
              />
            )
          })}
          {learningIndex?.blueprints?.[0] && (
            <NavLink
              to={`/simulations/${learningIndex.blueprints[0].id}`}
              className={() => navItemClass(pathname.startsWith('/simulations/'))}
              onClick={onClose}
            >
              {navLabel('simulations')}
            </NavLink>
          )}
        </NavGroup>

        {/* 公告試題（resource_catalog 順序：新到舊，樣題在後） */}
        <NavGroup label={NAV_GROUP_LABELS.exams} suffix={level.label}>
          {examItems.map((item) => (
            <SidebarLink key={item.to ?? item.label} item={item} onClose={onClose} />
          ))}
          {referenceItems.length > 0 && (
            <div>
              <button
                type="button"
                className="flex min-h-[max(2.5rem,var(--control-min-h))] w-full items-center gap-2 border-l-[3px] border-l-transparent py-2 pl-[1.1rem] pr-3 text-left text-meta text-on-dark-muted hover:bg-white/8 hover:text-on-dark"
                onClick={toggleReferences}
                aria-expanded={referencesOpen}
              >
                <span className="inline-block w-3 shrink-0" aria-hidden="true">{referencesOpen ? '▾' : '▸'}</span>
                {SECTION_LABELS.references}
              </button>
              {referencesOpen && referenceItems.map((item) => (
                <SidebarLink key={item.label} item={item} onClose={onClose} indent="pl-[2.25rem]" />
              ))}
            </div>
          )}
        </NavGroup>

        {/* 工具 */}
        <NavGroup label={NAV_GROUP_LABELS.tools}>
          <NavLink to="/outline" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('outline')}
          </NavLink>
          <NavLink to="/mindmap" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('mindmap')}
          </NavLink>
          <NavLink to="/concepts" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('concepts')}
          </NavLink>
          <NavLink to="/glossary" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('glossary')}
          </NavLink>
          <NavLink to="/images" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
            {navLabel('images')}
          </NavLink>
          {(learningIndex?.analysis?.length ?? 0) > 0 && (
            <NavLink to="/analysis/exams" className={({ isActive }) => navItemClass(isActive)} onClick={onClose}>
              {navLabel('analysis')}
            </NavLink>
          )}
        </NavGroup>
      </div>
    </aside>
  )
}

export default memo(Sidebar)
