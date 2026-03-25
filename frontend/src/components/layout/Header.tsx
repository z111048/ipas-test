interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="bg-primary text-white px-6 h-14 flex items-center justify-between sticky top-0 z-100 shadow-[0_2px_8px_rgba(0,0,0,0.3)]">
      <button
        className="md:hidden text-white text-xl mr-3 bg-transparent border-0 cursor-pointer p-1"
        onClick={onMenuClick}
        aria-label="選單"
      >
        ☰
      </button>
      <h1 className="text-[1.1rem] font-bold tracking-[0.5px] flex-1">
        📚 iPAS AI應用規劃師（初級）
      </h1>
      <span className="text-[0.8rem] opacity-70 hidden sm:block">科目一 × 科目二 完整備考系統</span>
    </header>
  )
}
