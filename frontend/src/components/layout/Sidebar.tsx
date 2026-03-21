import { NavLink } from 'react-router-dom'

interface NavItem {
  label: string
  to: string
}

interface NavSection {
  heading: string
  items: NavItem[]
}

const NAV_SECTIONS: NavSection[] = [
  {
    heading: '總覽',
    items: [{ label: '🏠 首頁', to: '/' }],
  },
  {
    heading: '科目一：人工智慧基礎概論',
    items: [
      { label: '📖 章節總覽', to: '/subject/s1' },
      { label: '✏️ 人工智慧概念', to: '/practice/s1/s1c1' },
      { label: '✏️ 資料處理與分析', to: '/practice/s1/s1c2' },
      { label: '✏️ 機器學習概念', to: '/practice/s1/s1c3' },
      { label: '✏️ 鑑別式AI與生成式AI', to: '/practice/s1/s1c4' },
      { label: '🎯 模擬考試（科目一）', to: '/exam/mock1' },
    ],
  },
  {
    heading: '科目二：生成式AI應用與規劃',
    items: [
      { label: '📖 章節總覽', to: '/subject/s2' },
      { label: '✏️ No Code / Low Code', to: '/practice/s2/s2c1' },
      { label: '✏️ 生成式AI應用與工具', to: '/practice/s2/s2c2' },
      { label: '✏️ 生成式AI導入評估規劃', to: '/practice/s2/s2c3' },
      { label: '🎯 模擬考試（科目二）', to: '/exam/mock2' },
    ],
  },
  {
    heading: '樣題練習',
    items: [{ label: '📝 考試樣題（114年9月版）', to: '/exam/sample' }],
  },
  {
    heading: '學習指引 科目一',
    items: [
      { label: '📖 人工智慧概念', to: '/guide/s1/s1c1' },
      { label: '📖 資料處理分析統計', to: '/guide/s1/s1c2' },
      { label: '📖 機器學習概念', to: '/guide/s1/s1c3' },
      { label: '📖 鑑別式╱生成式AI', to: '/guide/s1/s1c4' },
    ],
  },
  {
    heading: '學習指引 科目二',
    items: [
      { label: '📖 No Code / Low Code', to: '/guide/s2/s2c1' },
      { label: '📖 生成式AI應用與工具', to: '/guide/s2/s2c2' },
      { label: '📖 導入評估規劃', to: '/guide/s2/s2c3' },
    ],
  },
]

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const itemClass = ({ isActive }: { isActive: boolean }) =>
    `block py-[0.55rem] px-5 cursor-pointer text-[0.85rem] border-l-[3px] transition-all duration-150 no-underline ${
      isActive
        ? 'bg-white/10 border-l-accent text-white font-semibold'
        : 'border-l-transparent text-white/85 hover:bg-white/8 hover:text-white'
    }`

  return (
    <aside
      className={`
        fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-[260px] bg-primary text-white
        overflow-y-auto flex-shrink-0 pb-8 z-50 transition-transform duration-300
        md:relative md:top-auto md:left-auto md:h-full md:translate-x-0 md:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      {NAV_SECTIONS.map((section, si) => (
        <div key={si}>
          {si > 0 && <div className="h-px bg-white/10 mx-4 my-2" />}
          <div className="py-2">
            <div className="text-[0.7rem] uppercase tracking-widest text-white/50 px-4 pt-2 pb-1 font-semibold">
              {section.heading}
            </div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={itemClass}
                onClick={onClose}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </aside>
  )
}
