import { Link } from 'react-router-dom'
import { resourceLevels, resourceStats, type ResourceNavItem } from '../data/resourceRegistry'
import { learningArticleIndex } from '../data/articleLoaders'
import StatBox from '../components/shared/StatBox'

function statusLabel(status?: ResourceNavItem['status']) {
  if (status === 'pending') return '待建立'
  if (status === 'external') return '官方連結'
  return '已入庫'
}

function ResourceLink({ item }: { item: ResourceNavItem }) {
  const navigable = Boolean((item.to || item.externalUrl) && item.status !== 'pending')
  const content = (
    <>
      <span className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-semibold text-primary">
          {item.label}
          {navigable && (
            <span className="text-accent opacity-0 -translate-x-0.5 transition-all duration-150 group-hover:opacity-100 group-hover:translate-x-0" aria-hidden="true">
              →
            </span>
          )}
        </span>
        <span className={`shrink-0 ${item.status === 'pending' ? 'pill pill-muted' : 'pill'}`}>
          {statusLabel(item.status)}
        </span>
      </span>
      {item.detail && <span className="block text-[0.8rem] text-text-light mt-1">{item.detail}</span>}
    </>
  )

  const className = 'group block surface-compact px-4 py-3 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff]'
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

  const juniorPracticeTo = resourceLevels[0].subjects[0]?.practiceTo
  const middleGuideTo = resourceLevels[1].subjects[0]?.guideTo
  const firstExamTo = resourceLevels[0].exams[0]?.to
  const firstArticleTo = learningArticleIndex.articlesById[learningArticleIndex.flatArticleIds[0]]?.route ?? '/articles'

  return (
    <div className="page-shell">
      <div className="page-header mb-5 overflow-hidden relative">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/5 blur-2xl" aria-hidden="true" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="eyebrow mb-2">經濟部 iPAS 產業人才能力鑑定</div>
            <h1 className="text-[1.7rem] leading-tight font-bold text-primary mb-2">AI 應用規劃師備考平台</h1>
            <p className="text-[0.95rem] leading-7 text-text-light">
              整合初級與中級的官方學習指引、歷屆公告試題與 AI 模擬練習，依科目章節對齊評鑑範圍，提供一站式系統化備考路徑。
            </p>
            <div className="mt-4 flex flex-wrap gap-2.5">
              {juniorPracticeTo && (
                <Link to={juniorPracticeTo} className="btn-primary">開始初級章節練習</Link>
              )}
              <Link to={firstArticleTo} className="btn-outline">主題文章學習</Link>
              {middleGuideTo && (
                <Link to={middleGuideTo} className="btn-outline">中級學習指引</Link>
              )}
              {firstExamTo && (
                <Link to={firstExamTo} className="btn-muted">歷屆公告試題</Link>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2 lg:flex-col lg:items-end">
            <span className="pill">官方資料對齊</span>
            <span className="pill pill-muted">初級 / 中級雙軌</span>
            <span className="pill pill-muted">{learningArticleIndex.pathCount} 條主題路徑</span>
          </div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap mb-6">
        <StatBox value={resourceStats.junior.subjects + resourceStats.middle.subjects} label="考試科目" />
        <StatBox value={resourceStats.junior.chapters + resourceStats.middle.chapters} label="章節單元" />
        <StatBox value={learningArticleIndex.articleCount} label="主題文章" />
        <StatBox value={learningArticleIndex.pathCount} label="學習路徑" />
        <StatBox value={totalPractice} label="章節練習題" />
        <StatBox value={totalOfficial} label="官方試題 / 樣題" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-6">
        {resourceLevels.map((level) => {
          const stats = resourceStats[level.id]
          return (
            <section key={level.id} className="surface p-5">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-base font-bold text-white">
                    {level.label.charAt(0)}
                  </span>
                  <div>
                    <h2 className="text-xl font-semibold text-primary mb-1">{level.label}</h2>
                    <p className="text-[0.88rem] leading-6 text-text-light">{level.subtitle}</p>
                  </div>
                </div>
                <span className="pill shrink-0">
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
        <div className="eyebrow mb-1">Study path</div>
        <h2 className="section-title mb-4">建議備考流程</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            {
              step: '01',
              title: '確認科目與範圍',
              desc: '依級別選定要準備的科目，先讀主題式文章建立架構，再回到官方學習指引對照原始範圍。',
            },
            {
              step: '02',
              title: '章節練習鞏固概念',
              desc: '透過 AI 模擬章節練習題反覆檢測熟悉度；中級可搭配關鍵字整理快速複習中英文術語。',
            },
            {
              step: '03',
              title: '歷屆試題實戰驗收',
              desc: '以公告試題與官方樣題模擬作答；遇圖表題回到 PDF 圖片與表格檢視頁對照原始版面。',
            },
          ].map((s) => (
            <div key={s.step} className="surface-compact p-4">
              <div className="text-[1.4rem] font-bold tabular-nums text-accent/80 leading-none mb-2">{s.step}</div>
              <div className="font-semibold text-primary mb-1.5">{s.title}</div>
              <p className="text-[0.85rem] leading-6 text-text-light">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
