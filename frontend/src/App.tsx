import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { HashRouter, Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import Overlay from './components/layout/Overlay'
import Footer from './components/layout/Footer'
import AppErrorBoundary from './components/shared/AppErrorBoundary'

const HomePage = lazy(() => import('./pages/HomePage'))
const SubjectOverviewPage = lazy(() => import('./pages/SubjectOverviewPage'))
const PracticePage = lazy(() => import('./pages/PracticePage'))
const ExamPage = lazy(() => import('./pages/ExamPage'))
const GuidePage = lazy(() => import('./pages/GuidePage'))
const ImageGalleryPage = lazy(() => import('./pages/ImageGalleryPage'))
const VisualCardsPage = lazy(() => import('./pages/VisualCardsPage'))
const GlossaryPage = lazy(() => import('./pages/GlossaryPage'))
const OutlinePage = lazy(() => import('./pages/OutlinePage'))
const MindmapPage = lazy(() => import('./pages/MindmapPage'))
const ConceptsPage = lazy(() => import('./pages/ConceptsPage'))
const LearningArticlesPage = lazy(() => import('./pages/LearningArticlesPage'))
const LearningArticlePage = lazy(() => import('./pages/LearningArticlePage'))
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

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 })
    mainRef.current?.focus()
  }, [location.pathname])

  // Ctrl/Cmd + K 開搜尋；在輸入框裡也要能觸發，所以不排除 input 目標
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        openSearch()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openSearch])

  return (
    <div className="app-root flex flex-col min-h-screen bg-app-bg text-app-text">
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
      <div className="app-frame flex overflow-hidden h-[calc(100vh-3.5rem)]">
        <Sidebar
          id={sidebarId}
          isOpen={sidebarOpen}
          onClose={closeSidebar}
          restoreFocusRef={menuButtonRef}
        />
        <main
          id="main-content"
          tabIndex={-1}
          ref={mainRef}
          className={`app-main app-scroll-stable flex-1 min-h-0 ${mainOverflow} ${isGuideRoute ? '' : 'flex flex-col'} px-4 py-4 md:px-6 md:py-6 min-w-0 focus:outline-none`}
        >
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

export default function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppShell />
    </HashRouter>
  )
}
