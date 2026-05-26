interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
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
          <div className="hidden text-[0.72rem] text-white/60 sm:block">官方資料、學習指引、公告試題與章節練習</div>
        </div>
        <span className="hidden rounded-full border border-white/20 bg-white/10 px-3 py-1 text-[0.76rem] font-semibold text-white/85 sm:inline-flex">初級 / 中級</span>
      </div>
    </header>
  )
}
