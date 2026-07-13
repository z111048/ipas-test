import { Link } from 'react-router-dom'
import { resourceLevels } from '../../data/resourceRegistry'

const quickLinks = [
  { label: '主題文章', to: '/articles' },
  { label: '概念圖卡', to: '/visuals' },
  { label: '關鍵字整理', to: '/glossary' },
  { label: '圖片與表格檢視', to: '/images' },
]

export default function Footer() {
  const year = new Date().getFullYear()
  const firstExam = resourceLevels[0]?.exams[0]

  return (
    <footer className="page-shell mt-10 border-t border-border pt-6 pb-8 text-[0.82rem] text-text-light">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="sm:col-span-1">
          <div className="mb-1.5 font-bold text-primary">iPAS AI 應用規劃師備考平台</div>
          <p className="leading-6">
            對齊經濟部 iPAS 產業人才能力鑑定評鑑範圍，整合學習指引、歷屆公告試題與章節練習的自主備考資源。
          </p>
        </div>
        <div>
          <div className="mb-1.5 font-bold text-primary">快速入口</div>
          <ul className="m-0 list-none space-y-1 p-0">
            {quickLinks.map((l) => (
              <li key={l.to}>
                <Link to={l.to} className="no-underline text-text-light hover:text-accent">
                  {l.label}
                </Link>
              </li>
            ))}
            {firstExam?.to && (
              <li>
                <Link to={firstExam.to} className="no-underline text-text-light hover:text-accent">
                  歷屆公告試題
                </Link>
              </li>
            )}
          </ul>
        </div>
        <div>
          <div className="mb-1.5 font-bold text-primary">官方資源</div>
          <ul className="m-0 list-none space-y-1 p-0">
            <li>
              <a
                href="https://www.ipas.org.tw/"
                target="_blank"
                rel="noreferrer"
                className="no-underline text-text-light hover:text-accent"
              >
                iPAS 產業人才能力鑑定官網 ↗
              </a>
            </li>
            <li>
              <a
                href="https://www.ipas.org.tw/AIA"
                target="_blank"
                rel="noreferrer"
                className="no-underline text-text-light hover:text-accent"
              >
                AI 應用規劃師鑑定介紹 ↗
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="mt-6 border-t border-border pt-4 leading-6">
        <p className="m-0">
          本平台為自主學習輔助資源，非 iPAS 官方網站；學習指引與公告試題之著作權屬原發行單位，僅供備考研習之用。
        </p>
        <p className="m-0 mt-1">© {year} iPAS AI 應用規劃師備考平台</p>
      </div>
    </footer>
  )
}
