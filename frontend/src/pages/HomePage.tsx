import { Link } from 'react-router-dom'
import { resourceLevels, resourceStats, type ResourceNavItem } from '../data/resourceRegistry'
import StatBox from '../components/shared/StatBox'

function statusLabel(status?: ResourceNavItem['status']) {
  if (status === 'pending') return '待建立'
  if (status === 'external') return '官方連結'
  return '已入庫'
}

function ResourceLink({ item }: { item: ResourceNavItem }) {
  const content = (
    <>
      <span className="flex items-center justify-between gap-2">
        <span className="font-semibold text-primary">{item.label}</span>
        <span className="pill shrink-0">
          {statusLabel(item.status)}
        </span>
      </span>
      {item.detail && <span className="block text-[0.8rem] text-text-light mt-1">{item.detail}</span>}
    </>
  )

  const className = 'block surface-compact px-4 py-3 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff]'
  if (item.externalUrl) {
    return (
      <a href={item.externalUrl} target="_blank" rel="noreferrer" className={className}>
        {content}
      </a>
    )
  }
  if (!item.to || item.status === 'pending') {
    return (
      <div className="block surface-compact px-4 py-3 bg-[#f8fafc]">
        {content}
      </div>
    )
  }
  return (
    <Link to={item.to} className={className}>
      {content}
    </Link>
  )
}

export default function HomePage() {
  const totalPractice = resourceStats.junior.practiceQuestions + resourceStats.middle.practiceQuestions
  const totalOfficial = resourceStats.junior.officialQuestions + resourceStats.middle.officialQuestions

  return (
    <div className="page-shell">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Study workspace</div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary mb-1">iPAS AI應用規劃師備考平台</h1>
            <p className="max-w-3xl text-[0.92rem] leading-7 text-text-light">依初級與中級分流，清楚區分官方資料、公告試題、學習指引與章節練習狀態。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="pill">官方資料對齊</span>
            <span className="pill pill-muted">初級 / 中級</span>
          </div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap mb-6">
        <StatBox value={resourceStats.junior.subjects + resourceStats.middle.subjects} label="考試科目" />
        <StatBox value={resourceStats.junior.chapters + resourceStats.middle.chapters} label="章節單元" />
        <StatBox value={totalPractice} label="章節練習題" />
        <StatBox value={totalOfficial} label="官方試題/樣題" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-6">
        {resourceLevels.map((level) => {
          const stats = resourceStats[level.id]
          return (
            <section key={level.id} className="surface p-5">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-xl font-semibold text-primary mb-1">{level.label}</h2>
                  <p className="text-[0.88rem] text-text-light">{level.subtitle}</p>
                </div>
                <span className="pill">
                  {stats.subjects} 科 / {stats.chapters} 章
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                {level.subjects.map((subject) => (
                  <ResourceLink
                    key={subject.id}
                    item={{
                      label: subject.label,
                      detail: `${subject.chapters} 個章節，${subject.practiceLabel}`,
                      to: subject.overviewTo,
                      status: 'available',
                    }}
                  />
                ))}
              </div>

              <div className="section-title mb-2">公告試題與樣題</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                {[...level.exams, ...level.samples].map((item) => (
                  <ResourceLink key={item.label} item={item} />
                ))}
              </div>

              <div className="section-title mb-2">官方參考資料</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {level.references.map((item) => (
                  <ResourceLink key={item.label} item={item} />
                ))}
              </div>
            </section>
          )
        })}
      </div>

      <div className="surface p-5 mb-4">
        <h2 className="section-title mb-3">考試說明</h2>
        <div className="overflow-x-auto -webkit-overflow-scrolling-touch">
          <table className="table-soft text-[0.88rem] min-w-[520px]">
            <thead>
              <tr>
                <th >級別</th>
                <th >科目</th>
                <th >目前網站狀態</th>
              </tr>
            </thead>
            <tbody>
              {resourceLevels.map((level) => (
                <tr key={level.id}>
                  <td className="font-semibold text-primary">{level.label}</td>
                  <td >{level.subjects.map((subject) => subject.shortLabel).join('、')}</td>
                  <td >{level.subtitle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="surface p-5">
        <h2 className="section-title mb-3">備考建議</h2>
        <ol className="ml-5 space-y-1 text-[0.9rem] leading-7">
          <li>先依級別確認要準備的科目，再閱讀對應學習指引。</li>
          <li>初級與中級都可使用章節練習題建立概念熟悉度，中級可搭配關鍵字整理快速複習術語。</li>
          <li>遇到圖片或表格題，使用 PDF 圖片與表格檢視頁回看原始版面。</li>
          <li>中級三個科目可先用關鍵字表建立中英文術語對照，再回到章節題檢查理解。</li>
        </ol>
      </div>
    </div>
  )
}
