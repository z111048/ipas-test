import { Link } from 'react-router-dom'
import { resourceLevels } from '../../data/resourceRegistry'
import { NAV_LABELS, SITE_NAME, navLabel, type NavLabelKey } from '../../constants/navLabels'

const quickLinkKeys: NavLabelKey[] = ['articles', 'visuals', 'glossary', 'concepts', 'images']
const quickLinks = quickLinkKeys.map((key) => ({ label: navLabel(key), to: NAV_LABELS[key].route }))

/** Standalone footer link: 44px tall on touch / narrow screens (.text-link), muted color. */
const footerLinkClass = 'text-link font-normal text-text-light hover:text-accent'

export default function Footer() {
  const year = new Date().getFullYear()
  const firstExam = resourceLevels[0]?.exams[0]

  return (
    <footer className="page-shell mt-10 border-t border-border pt-6 pb-8 text-meta text-text-light">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="sm:col-span-1">
          <div className="mb-1.5 font-bold text-primary">{SITE_NAME}</div>
          <p className="leading-6">
            對齊經濟部 iPAS 產業人才能力鑑定評鑑範圍，整合學習指引、歷屆公告試題與章節練習的自主備考資源。
          </p>
        </div>
        <div>
          <div className="mb-1.5 font-bold text-primary">快速入口</div>
          <ul className="m-0 list-none p-0">
            {quickLinks.map((l) => (
              <li key={l.to}>
                <Link to={l.to} className={footerLinkClass}>
                  {l.label}
                </Link>
              </li>
            ))}
            {firstExam?.to && (
              <li>
                <Link to={firstExam.to} className={footerLinkClass}>
                  {navLabel('exam')}
                </Link>
              </li>
            )}
          </ul>
        </div>
        <div>
          <div className="mb-1.5 font-bold text-primary">官方資源</div>
          <ul className="m-0 list-none p-0">
            <li>
              <a
                href="https://www.ipas.org.tw/"
                target="_blank"
                rel="noreferrer"
                className={footerLinkClass}
              >
                iPAS 產業人才能力鑑定官網 ↗
              </a>
            </li>
            <li>
              <a
                href="https://www.ipas.org.tw/AIA"
                target="_blank"
                rel="noreferrer"
                className={footerLinkClass}
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
        <p className="m-0 mt-1">© {year} {SITE_NAME}</p>
      </div>
    </footer>
  )
}
