import { useLocation } from 'react-router-dom'

interface HeaderProps {
  onMenuClick: () => void
  onSearchClick: () => void
}

function sectionLabel(pathname: string): string | null {
  if (pathname === '/') return '首頁'
  if (pathname.startsWith('/subject/')) return '科目總覽'
  if (pathname.startsWith('/practice/')) return '章節練習'
  if (pathname.startsWith('/exam/')) return '測驗'
  if (pathname.startsWith('/guide/')) return '學習指引'
  if (pathname.startsWith('/articles')) return '主題文章'
  if (pathname.startsWith('/visuals')) return '概念圖卡'
  if (pathname.startsWith('/glossary')) return '名詞解釋'
  if (pathname.startsWith('/outline')) return '完整目錄'
  if (pathname.startsWith('/images')) return '圖片總覽'
  return null
}

export default function Header({ onMenuClick, onSearchClick }: HeaderProps) {
  const location = useLocation()
  const section = sectionLabel(location.pathname)

  return (
    <header className="sticky top-0 z-100 h-14 border-b border-white/10 bg-primary text-white shadow-[0_8px_24px_rgba(15,23,42,0.18)]">
      <div className="flex h-full items-center justify-between gap-4 px-4 md:px-6">
        <button
          className="md:hidden inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/20 bg-white/8 text-white text-lg cursor-pointer"
          onClick={onMenuClick}
          aria-label="選單"
        >
          ☰
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[1rem] font-bold tracking-0">iPAS AI應用規劃師備考平台</h1>
          <div className="hidden text-[0.72rem] text-white/60 sm:flex sm:items-center sm:gap-1.5">
            <span>官方資料、學習指引、公告試題與章節練習</span>
            {section && (
              <>
                <span aria-hidden="true" className="text-white/30">·</span>
                <span className="font-semibold text-white/80">{section}</span>
              </>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onSearchClick}
          className="inline-flex shrink-0 items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[0.76rem] text-white/85 hover:bg-white/16"
          aria-label="搜尋學習指引"
        >
          <span aria-hidden="true">🔍</span>
          <span className="hidden sm:inline">搜尋</span>
          <kbd className="hidden rounded border border-white/25 px-1 text-[0.65rem] text-white/60 md:inline">Ctrl K</kbd>
        </button>
      </div>
    </header>
  )
}
