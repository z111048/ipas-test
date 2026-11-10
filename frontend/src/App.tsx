import { lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { HashRouter, Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import Overlay from './components/layout/Overlay'
import Footer from './components/layout/Footer'
import AppErrorBoundary from './components/shared/AppErrorBoundary'
import { useFocusModeActive } from './hooks/useFocusMode'
import { SeasonalProvider } from './features/seasonal'
import { recordLastVisit } from './utils/lastVisit'
import {
  importExamPage,
  importGuidePage,
  importPracticePage,
  installRoutePrefetch,
} from './utils/routePrefetch'

const HomePage = lazy(() => import('./pages/HomePage'))
const SubjectOverviewPage = lazy(() => import('./pages/SubjectOverviewPage'))
const PracticePage = lazy(importPracticePage)
const ExamPage = lazy(importExamPage)
const GuidePage = lazy(importGuidePage)
const ImageGalleryPage = lazy(() => import('./pages/ImageGalleryPage'))
const VisualCardsPage = lazy(() => import('./pages/VisualCardsPage'))
const GlossaryPage = lazy(() => import('./pages/GlossaryPage'))
const OutlinePage = lazy(() => import('./pages/OutlinePage'))
const MindmapPage = lazy(() => import('./pages/MindmapPage'))
const ConceptsPage = lazy(() => import('./pages/ConceptsPage'))
const LearningArticlesPage = lazy(() => import('./pages/LearningArticlesPage'))
const LearningArticlePage = lazy(() => import('./pages/LearningArticlePage'))
const LearnPage = lazy(() => import('./features/learning/LearnPage'))
const ProjectsPage = lazy(() => import('./features/learning/ProjectsPage'))
const LabPage = lazy(() => import('./features/learning/LabPage'))
const SimulationPage = lazy(() => import('./features/learning/SimulationPage'))
const LearningAnalysisPage = lazy(() => import('./features/learning/LearningAnalysisPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
// 搜尋對話框連同 204 KB 索引都不進首頁 bundle，第一次開啟才載入
const GuideSearchDialog = lazy(() => import('./components/search/GuideSearchDialog'))

function PageSkeleton() {
  return (
    <div className="page-shell w-full animate-pulse" aria-hidden="true">
      <div className="mb-5 h-40 rounded-xl bg-slate-200/70 md:h-48" />
      <div className="mb-6 flex flex-wrap gap-3">
        <div className="h-20 min-w-[112px] flex-1 rounded-xl bg-slate-200/70" />
        <div className="h-20 min-w-[112px] flex-1 rounded-xl bg-slate-200/70" />
        <div className="h-20 min-w-[112px] flex-1 rounded-xl bg-slate-200/70" />
      </div>
      <div className="mb-6 h-56 rounded-xl bg-slate-200/70" />
      <div className="h-56 rounded-xl bg-slate-200/70" />
    </div>
  )
}

function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const searchButtonRef = useRef<HTMLButtonElement>(null)
  const searchRestoreRef = useRef<HTMLElement>(null)
  const sidebarId = 'primary-navigation'
  const isGuideRoute = location.pathname.startsWith('/guide/')
  const mainOverflow = isGuideRoute ? 'overflow-hidden' : 'overflow-y-scroll'
  const closeSidebar = useCallback(() => setSidebarOpen(false), [])
  // 專注模式（useFocusMode）：手機隱藏 Header 與選單按鈕，桌機收合 Sidebar
  const focusMode = useFocusModeActive()
  const openSearch = useCallback(() => {
    // Page-owned dialogs/drawers must remain the only active focus trap.
    // The mobile sidebar is the one exception: replace it with search.
    const activeModal = document.querySelector<HTMLElement>(
      '[aria-modal="true"]:not([aria-hidden="true"])',
    )
    if (activeModal && activeModal.id !== sidebarId) return
    const activeElement = document.activeElement
    searchRestoreRef.current = activeModal?.id === sidebarId
      ? searchButtonRef.current
      : activeElement instanceof HTMLElement && activeElement !== document.body
        ? activeElement
        : searchButtonRef.current
    setSidebarOpen(false)
    setSearchOpen(true)
  }, [sidebarId])
  const toggleSidebar = useCallback(() => {
    const activeModal = document.querySelector<HTMLElement>(
      '[aria-modal="true"]:not([aria-hidden="true"])',
    )
    if (activeModal && activeModal.id !== sidebarId) return
    setSearchOpen(false)
    setSidebarOpen((open) => !open)
  }, [sidebarId])

  // 任何導頁（含頁內連結、瀏覽器上一頁）都關閉手機抽屜
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname, location.search])

  useEffect(() => {
    if (focusMode) setSidebarOpen(false)
  }, [focusMode])

  useEffect(() => {
    recordLastVisit(location.pathname)
  }, [location.pathname])

  useEffect(() => installRoutePrefetch(), [])

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 })
    mainRef.current?.focus()
  }, [location.pathname])

  // Ctrl/Cmd + K 開搜尋；在輸入框裡也要能觸發，所以不排除 input 目標。
  // 專注模式（考試作答中）不開搜尋，避免考生誤觸離開作答畫面。
  useEffect(() => {
    if (focusMode) return
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        openSearch()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openSearch, focusMode])

  return (
    <div
      className={`app-root flex flex-col min-h-screen bg-app-bg text-app-text ${
        focusMode ? 'max-md:[--app-header-h:0px]' : ''
      }`}
      data-focus-mode={focusMode ? 'true' : undefined}
    >
      <a
        href="#main-content"
        className="skip-link"
        onClick={(event) => {
          // HashRouter owns the URL fragment — a native #main-content jump
          // would be routed as a navigation to /main-content.
          event.preventDefault()
          mainRef.current?.focus()
        }}
      >
        跳至主要內容
      </a>
      <Header
        menuButtonRef={menuButtonRef}
        searchButtonRef={searchButtonRef}
        sidebarId={sidebarId}
        sidebarOpen={sidebarOpen}
        onMenuClick={toggleSidebar}
        onSearchClick={openSearch}
        hiddenOnMobile={focusMode}
      />
      {searchOpen && (
        <Suspense fallback={null}>
          <GuideSearchDialog
            open={searchOpen}
            onClose={() => setSearchOpen(false)}
            restoreFocusRef={searchRestoreRef}
          />
        </Suspense>
      )}
      <Overlay isOpen={sidebarOpen} onClick={closeSidebar} />
      <div
        className={`app-frame flex overflow-hidden h-[calc(100vh-3.5rem)] ${
          focusMode ? 'max-md:mt-[var(--app-safe-top)]' : ''
        }`}
      >
        <Sidebar
          id={sidebarId}
          isOpen={sidebarOpen}
          onClose={closeSidebar}
          onSearch={openSearch}
          restoreFocusRef={menuButtonRef}
          collapsed={focusMode}
        />
        <main
          id="main-content"
          tabIndex={-1}
          ref={mainRef}
          className={`app-main app-scroll-stable relative flex-1 min-h-0 ${mainOverflow} ${isGuideRoute ? '' : 'flex flex-col'} px-4 py-4 md:px-6 md:py-6 min-w-0 focus:outline-none`}
        >
          {/* 一般頁：內容區至少撐滿 main 可視高度，頁尾永遠在第一屏下方，載入前後不會被推動。
              guide 路由由 GuidePage 自己管理版面，用 contents 讓這層不影響排版。 */}
          <div className={isGuideRoute ? 'route-view contents' : 'route-view min-h-full w-full shrink-0'}>
          <AppErrorBoundary resetKey={location.key}>
            <Suspense fallback={<PageSkeleton />}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/subject/:subjectId" element={<SubjectOverviewPage />} />
                <Route path="/practice/:subjectId/:chapterId" element={<PracticePage />} />
                <Route path="/practice/:subjectId/:chapterId/:practiceSet" element={<PracticePage />} />
                <Route path="/exam/:examKey" element={<ExamPage />} />
                <Route path="/guide/:subjectId/:chapterId" element={<GuidePage />} />
                <Route path="/articles" element={<LearningArticlesPage />} />
                <Route path="/articles/:articleId" element={<LearningArticlePage />} />
                <Route path="/learn" element={<LearnPage />} />
                <Route path="/learn/:unitId" element={<LearnPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/:projectId" element={<ProjectsPage />} />
                <Route path="/labs/:labId" element={<LabPage />} />
                <Route path="/simulations/:blueprintId" element={<SimulationPage />} />
                <Route path="/analysis/exams" element={<LearningAnalysisPage />} />
                <Route path="/visuals" element={<VisualCardsPage />} />
                <Route path="/images" element={<ImageGalleryPage />} />
                <Route path="/glossary" element={<GlossaryPage />} />
                <Route path="/outline" element={<OutlinePage />} />
                <Route path="/mindmap" element={<MindmapPage />} />
                <Route path="/concepts" element={<ConceptsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </AppErrorBoundary>
          </div>
          {!isGuideRoute && (
            <div className="mt-auto w-full">
              <Footer />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

/** 節慶主題（features/seasonal）：要讀路由與專注模式，所以放在 HashRouter 裡、包住整個 AppShell。 */
function SeasonalRoot({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const focusMode = useFocusModeActive()
  return (
    <SeasonalProvider pathname={pathname} focusMode={focusMode}>
      {children}
    </SeasonalProvider>
  )
}

export default function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SeasonalRoot>
        <AppShell />
      </SeasonalRoot>
    </HashRouter>
  )
}
