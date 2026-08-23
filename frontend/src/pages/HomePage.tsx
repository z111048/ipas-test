import { Link } from 'react-router-dom'
import {
  resourceLevels,
  resourceStats,
  resourceSummary,
  type ResourceNavItem,
  type SubjectResource,
} from '../data/resourceRegistry'
import { learningArticleIndex } from '../data/articleLoaders'
import StatBox from '../components/shared/StatBox'

function statusLabel(status?: ResourceNavItem['status']) {
  if (status === 'pending') return '待建立'
  if (status === 'external') return '官方連結'
  return '已入庫'
}

function ResourceLink({ item, compact = false }: { item: ResourceNavItem; compact?: boolean }) {
  const content = (
    <>
      <span className="flex items-center justify-between gap-2">
        <span className="min-w-0 font-semibold text-primary">
          {item.label}
        </span>
        <span className={`shrink-0 ${item.status === 'pending' ? 'pill pill-muted' : 'pill'}`}>
          {statusLabel(item.status)}
        </span>
      </span>
      {item.detail && <span className="mt-1 block text-[0.8rem] text-text-light">{item.detail}</span>}
    </>
  )

  const className = `group block surface-compact surface-hover no-underline hover:bg-[#f8fbff] ${
    compact ? 'px-3 py-2.5' : 'px-4 py-3'
  }`
  if (item.externalUrl) {
    return (
      <a href={item.externalUrl} target="_blank" rel="noreferrer" className={className}>
        {content}
      </a>
    )
  }
  if (!item.to || item.status === 'pending') {
    return (
      <div className={`surface-compact bg-[#f8fafc] ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
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

function SubjectTaskLink({
  to,
  label,
  detail,
  primary = false,
}: {
  to?: string
  label: string
  detail: string
  primary?: boolean
}) {
  if (!to) {
    return (
      <div className="rounded-lg border border-border bg-[#f8fafc] px-3 py-2.5 text-[0.84rem] text-text-light">
        <span className="block font-semibold text-text-light">{label}</span>
        <span className="mt-0.5 block text-[0.74rem] leading-5">{detail}</span>
      </div>
    )
  }

  return (
    <Link
      to={to}
      className={`min-h-11 rounded-lg border px-3 py-2.5 text-[0.84rem] no-underline transition-colors ${
        primary
          ? 'border-accent bg-accent text-white hover:bg-accent-hover'
          : 'border-border bg-white text-primary hover:border-accent hover:bg-[#f8fbff]'
      }`}
    >
      <span className="block font-semibold">{label}</span>
      <span className={`mt-0.5 block text-[0.74rem] leading-5 ${primary ? 'text-white/78' : 'text-text-light'}`}>
        {detail}
      </span>
    </Link>
  )
}

function practiceTarget(subject: SubjectResource) {
  if (subject.practiceStatus === 'available' && subject.practiceTo) {
    return { to: subject.practiceTo, label: '練', detail: subject.practiceLabel }
  }
  if (subject.guideExercisePracticeTo) {
    return { to: subject.guideExercisePracticeTo, label: '練', detail: '學習指引練習' }
  }
  return { to: undefined, label: '練', detail: subject.practiceLabel }
}

export default function HomePage() {
  const totalPractice = resourceStats.junior.practiceQuestions + resourceStats.middle.practiceQuestions
  const totalOfficial = resourceStats.junior.officialQuestions + resourceStats.middle.officialQuestions
  const totalVisuals = resourceSummary.visuals?.total ?? 0
  const firstArticleTo = learningArticleIndex.articlesById[learningArticleIndex.flatArticleIds[0]]?.route ?? '/articles'
  const firstExamTo = resourceLevels[0].exams[0]?.to

  return (
    <div className="page-shell">
      <section className="hero-panel mb-5 px-4 py-5 sm:px-6 md:px-8 md:py-7">
        <div className="hero-grid" aria-hidden="true" />
        <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(260px,340px)] lg:items-end">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap gap-2">
              <span className="hero-chip">經濟部 iPAS 產業人才能力鑑定</span>
              <span className="hero-chip">初級・中級</span>
            </div>
            <h1 className="mb-3 text-[1.8rem] font-black leading-[1.22] tracking-0 text-white md:text-[2.3rem]">
              AI 應用規劃師備考平台
            </h1>
            <p className="max-w-2xl text-[0.95rem] leading-7 text-white/76">
              先選級別與科目，再依章節讀指引、做練習、驗收公告試題。
            </p>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <button
                type="button"
                className="btn-hero min-h-11"
                onClick={() => document.getElementById('choose-subject')?.scrollIntoView({
                  behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
                  block: 'start',
                })}
              >
                選擇級別與科目
              </button>
              <Link to={firstArticleTo} className="btn-hero-ghost min-h-11">主題文章</Link>
              {firstExamTo && <Link to={firstExamTo} className="btn-hero-ghost min-h-11">公告試題</Link>}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 border-t border-white/15 pt-4 text-white lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{resourceStats.junior.subjects + resourceStats.middle.subjects}</div>
              <div className="mt-1 text-[0.72rem] font-medium text-white/60">科目</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalPractice}</div>
              <div className="mt-1 text-[0.72rem] font-medium text-white/60">練習題</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalOfficial}</div>
              <div className="mt-1 text-[0.72rem] font-medium text-white/60">公告題</div>
            </div>
          </div>
        </div>
      </section>

      <section id="choose-subject" className="surface mb-6 p-4 sm:p-5 scroll-mt-4">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="eyebrow mb-1">Start here</div>
            <h2 className="section-title">選擇級別與科目</h2>
          </div>
          <div className="text-[0.82rem] leading-6 text-text-light">
            每科都可從「讀、練、考」進入；尚未建置的資源會顯示狀態。
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {resourceLevels.map((level) => {
            const stats = resourceStats[level.id]
            return (
              <section key={level.id} className="surface-compact p-4">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-primary">{level.label}</h3>
                    <p className="mt-1 text-[0.84rem] leading-6 text-text-light">{level.subtitle}</p>
                  </div>
                  <span className="pill shrink-0">{stats.subjects} 科 / {stats.chapters} 章</span>
                </div>
                <div className="space-y-3">
                  {level.subjects.map((subject) => {
                    const practice = practiceTarget(subject)
                    return (
                      <article key={subject.id} className="rounded-lg border border-border bg-white p-3">
                        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <Link to={subject.overviewTo ?? subject.guideTo ?? '/'} className="font-semibold text-primary no-underline hover:text-accent">
                              {subject.label}
                            </Link>
                            <div className="mt-1 text-[0.78rem] text-text-light">
                              {subject.chapters} 個章節
                            </div>
                          </div>
                          <Link to={subject.overviewTo ?? subject.guideTo ?? '/'} className="btn-outline min-h-11 shrink-0">
                            科目總覽
                          </Link>
                        </div>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                          <SubjectTaskLink
                            to={subject.guideTo}
                            label="讀"
                            detail="學習指引"
                            primary
                          />
                          <SubjectTaskLink
                            to={practice.to}
                            label={practice.label}
                            detail={practice.detail}
                          />
                          <SubjectTaskLink
                            to={subject.examTo}
                            label="考"
                            detail="公告試題"
                          />
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      </section>

      <div className="mb-6 flex flex-wrap gap-3">
        <StatBox value={resourceStats.junior.chapters + resourceStats.middle.chapters} label="章節單元" />
        <StatBox value={learningArticleIndex.articleCount} label="主題文章" />
        <StatBox value={learningArticleIndex.pathCount} label="學習路徑" />
        {totalVisuals > 0 && <StatBox value={totalVisuals} label="概念圖卡" />}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {resourceLevels.map((level) => (
          <section key={level.id} className="surface p-4 sm:p-5">
            <div className="mb-4">
              <div className="eyebrow mb-1">{level.label}</div>
              <h2 className="section-title">公告試題與官方資料</h2>
            </div>
            <div className="section-title mb-2 text-[0.84rem]">公告試題與樣題</div>
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {[...level.exams, ...level.samples].map((item) => (
                <ResourceLink key={item.label} item={item} compact />
              ))}
            </div>
            <div className="section-title mb-2 text-[0.84rem]">官方參考資料</div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {level.references.map((item) => (
                <ResourceLink key={item.label} item={item} compact />
              ))}
            </div>
          </section>
        ))}
      </div>

      <section className="surface mt-6 p-4 sm:p-5">
        <div className="eyebrow mb-1">Study path</div>
        <h2 className="section-title mb-3">備考流程</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="surface-compact p-4">
            <div className="mb-1 text-[0.8rem] font-semibold text-accent">01 選科目</div>
            <p className="text-[0.85rem] leading-6 text-text-light">先確認級別與科目，再進科目總覽查看章節範圍。</p>
          </div>
          <div className="surface-compact p-4">
            <div className="mb-1 text-[0.8rem] font-semibold text-accent">02 讀與練</div>
            <p className="text-[0.85rem] leading-6 text-text-light">每章先讀主題文章或學習指引，再用可用練習題檢查理解。</p>
          </div>
          <div className="surface-compact p-4">
            <div className="mb-1 text-[0.8rem] font-semibold text-accent">03 做整卷</div>
            <p className="text-[0.85rem] leading-6 text-text-light">最後用公告試題與樣題驗收，錯題再回到章節補強。</p>
          </div>
        </div>
      </section>
    </div>
  )
}
