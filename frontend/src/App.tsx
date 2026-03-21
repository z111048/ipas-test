import { useState } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import Overlay from './components/layout/Overlay'
import HomePage from './pages/HomePage'
import SubjectOverviewPage from './pages/SubjectOverviewPage'
import PracticePage from './pages/PracticePage'
import ExamPage from './pages/ExamPage'
import GuidePage from './pages/GuidePage'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="flex flex-col min-h-screen bg-app-bg text-app-text">
        <Header onMenuClick={() => setSidebarOpen((o) => !o)} />
        <Overlay isOpen={sidebarOpen} onClick={() => setSidebarOpen(false)} />
        <div className="flex flex-1 overflow-hidden h-[calc(100vh-3.5rem)]">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <main className="flex-1 overflow-y-auto p-4 md:p-6 min-w-0">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/subject/:subjectId" element={<SubjectOverviewPage />} />
              <Route path="/practice/:subjectId/:chapterId" element={<PracticePage />} />
              <Route path="/exam/:examKey" element={<ExamPage />} />
              <Route path="/guide/:subjectId/:chapterId" element={<GuidePage />} />
            </Routes>
          </main>
        </div>
      </div>
    </HashRouter>
  )
}
