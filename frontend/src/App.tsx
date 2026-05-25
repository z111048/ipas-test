import { lazy, Suspense, useState } from 'react'
import { HashRouter, Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import Overlay from './components/layout/Overlay'

const HomePage = lazy(() => import('./pages/HomePage'))
const SubjectOverviewPage = lazy(() => import('./pages/SubjectOverviewPage'))
const PracticePage = lazy(() => import('./pages/PracticePage'))
const ExamPage = lazy(() => import('./pages/ExamPage'))
const GuidePage = lazy(() => import('./pages/GuidePage'))
const ImageGalleryPage = lazy(() => import('./pages/ImageGalleryPage'))
const GlossaryPage = lazy(() => import('./pages/GlossaryPage'))

function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const isGuideRoute = location.pathname.startsWith('/guide/')
  const mainOverflow = isGuideRoute ? 'overflow-hidden' : 'overflow-y-scroll'

  return (
    <div className="flex flex-col min-h-screen bg-app-bg text-app-text">
      <Header onMenuClick={() => setSidebarOpen((o) => !o)} />
      <Overlay isOpen={sidebarOpen} onClick={() => setSidebarOpen(false)} />
      <div className="flex flex-1 overflow-hidden h-[calc(100vh-3.5rem)]">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className={`app-scroll-stable flex-1 min-h-0 ${mainOverflow} p-4 md:p-6 min-w-0`}>
          <Suspense fallback={<div className="text-text-light p-4">頁面載入中...</div>}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/subject/:subjectId" element={<SubjectOverviewPage />} />
              <Route path="/practice/:subjectId/:chapterId" element={<PracticePage />} />
              <Route path="/practice/:subjectId/:chapterId/:practiceSet" element={<PracticePage />} />
              <Route path="/exam/:examKey" element={<ExamPage />} />
              <Route path="/guide/:subjectId/:chapterId" element={<GuidePage />} />
              <Route path="/images" element={<ImageGalleryPage />} />
              <Route path="/glossary" element={<GlossaryPage />} />
            </Routes>
          </Suspense>
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
