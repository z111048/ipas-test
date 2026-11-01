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
import { PageHeader, subjectOptionById } from '../components/ui'
import { SECTION_LABELS, SITE_NAME, navLabel } from '../constants/navLabels'

function statusLabel(status?: ResourceNavItem['status']) {
  if (status === 'pending') return '待建立'
  if (status === 'external') return '官方連結'
  return null
}

function ResourceLink({ item, compact = false }: { item: ResourceNavItem; compact?: boolean }) {
  const content = (
    <>
      <span className="flex items-center justify-between gap-2">
        <span className="min-w-0 font-semibold text-primary">
          {item.label}
        </span>
        {statusLabel(item.status) && (
          <span className={`shrink-0 ${item.status === 'pending' ? 'pill pill-muted' : 'pill'}`}>
            {statusLabel(item.status)}
          </span>
        )}
      </span>
      {item.detail && <span className="mt-1 block text-meta text-text-light">{item.detail}</span>}
    </>
  )

  const className = `group block min-h-11 surface-compact surface-hover no-underline hover:bg-accent-soft ${
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
      <div className={`surface-compact bg-unanswered-soft ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
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
      <div className="rounded-lg border border-border bg-unanswered-soft px-2.5 py-2.5 text-ui sm:px-3 text-text-light">
        <span className="block font-semibold text-text-light">{label}</span>
        <span className="mt-0.5 block text-caption leading-5">{detail}</span>
      </div>
    )
  }

  return (
    <Link
      to={to}
      className={`min-h-11 rounded-lg border px-2.5 py-2.5 text-ui no-underline sm:px-3 transition-colors ${
        primary
          ? 'border-accent bg-accent text-white hover:bg-accent-hover'
          : 'border-border bg-white text-primary hover:border-accent hover:bg-accent-soft'
      }`}
    >
      <span className="block font-semibold">{label}</span>
      <span className={`mt-0.5 block text-caption leading-5 ${primary ? 'text-on-dark-muted' : 'text-text-light'}`}>
        {detail}
      </span>
    </Link>
  )
}

function practiceTarget(subject: SubjectResource) {
  if (subject.practiceStatus === 'available' && subject.practiceTo) {
    return { to: subject.practiceTo, label: navLabel('practice'), detail: '逐章檢查理解' }
  }
  if (subject.guideExercisePracticeTo) {
    return { to: subject.guideExercisePracticeTo, label: navLabel('guidePractice'), detail: '學習指引內附題目' }
  }
  return { to: undefined, label: navLabel('practice'), detail: '待建立' }
}

export default function HomePage() {
  const totalPractice = resourceStats.junior.practiceQuestions + resourceStats.middle.practiceQuestions
  const totalOfficial = resourceStats.junior.officialQuestions + resourceStats.middle.officialQuestions
  const totalVisuals = resourceSummary.visuals?.total ?? 0
  const firstArticleTo = learningArticleIndex.articlesById[learningArticleIndex.flatArticleIds[0]]?.route ?? '/articles'
  const firstExamTo = resourceLevels[0].exams[0]?.to

  return (
    <div className="page-shell">
      <PageHeader
        variant="hero"
        className="mb-5"
        eyebrow={
          <>
            <span className="hero-chip">經濟部 iPAS 產業人才能力鑑定</span>
            <span className="hero-chip">初級・中級</span>
          </>
        }
        title={SITE_NAME}
        description="先選級別與科目，再依章節讀指引、做練習、驗收公告試題。"
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-hero hidden sm:inline-flex"
              onClick={() => document.getElementById('choose-subject')?.scrollIntoView({
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
                block: 'start',
              })}
            >
              選擇級別與科目
            </button>
            <Link to={firstArticleTo} className="btn-hero-ghost">{navLabel('articles')}</Link>
            {firstExamTo && <Link to={firstExamTo} className="btn-hero-ghost">{navLabel('exam')}</Link>}
          </div>
        }
        asideClassName="hidden sm:block"
        aside={
          <div className="grid grid-cols-3 gap-3 border-t border-white/15 pt-4 text-white lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{resourceStats.junior.subjects + resourceStats.middle.subjects}</div>
              <div className="mt-1 text-caption font-medium text-on-dark-muted">科目</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalPractice}</div>
              <div className="mt-1 text-caption font-medium text-on-dark-muted">練習題</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalOfficial}</div>
              <div className="mt-1 text-caption font-medium text-on-dark-muted">{navLabel('exam')}題數</div>
            </div>
          </div>
        }
      />

      <section id="choose-subject" className="surface mb-6 p-4 sm:p-5 scroll-mt-4">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="eyebrow mb-1">從這裡開始</div>
            <h2 className="section-title">選擇級別與科目</h2>
          </div>
          <div className="hidden text-meta leading-6 text-text-light sm:block">
            每科都可從學習指引、練習與公告試題進入；尚未建置的資源會顯示狀態。
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
                    <p className="mt-1 text-ui leading-6 text-text-light">{level.subtitle}</p>
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
                            <Link to={subject.overviewTo ?? subject.guideTo ?? '/'} className="text-link text-primary hover:text-accent">
                              {subjectOptionById(subject.id)?.fullLabel ?? subject.label}
                            </Link>
                            <div className="text-meta text-text-light">
                              {subject.chapters} 個章節
                            </div>
                          </div>
                          <Link to={subject.overviewTo ?? subject.guideTo ?? '/'} className="btn-outline btn-sm shrink-0">
                            {navLabel('subject')}
                          </Link>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <SubjectTaskLink
                            to={subject.guideTo}
                            label={navLabel('guide')}
                            detail="先讀章節重點"
                            primary
                          />
                          <SubjectTaskLink
                            to={practice.to}
                            label={practice.label}
                            detail={practice.detail}
                          />
                          <SubjectTaskLink
                            to={subject.examTo}
                            label={navLabel('exam')}
                            detail="整卷驗收"
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
        <StatBox value={learningArticleIndex.articleCount} label={navLabel('articles')} />
        <StatBox value={learningArticleIndex.pathCount} label="學習路徑" />
        {totalVisuals > 0 && <StatBox value={totalVisuals} label={navLabel('visuals')} />}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {resourceLevels.map((level) => (
          <section key={level.id} className="surface p-4 sm:p-5">
            <div className="mb-4">
              <div className="eyebrow mb-1">{level.label}</div>
              <h2 className="section-title">{SECTION_LABELS.exams}與{SECTION_LABELS.references}</h2>
            </div>
            <h3 className="section-title mb-2 text-ui">{SECTION_LABELS.exams}與樣題</h3>
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {[...level.exams, ...level.samples].map((item) => (
                <ResourceLink key={item.label} item={item} compact />
              ))}
            </div>
            <h3 className="section-title mb-2 text-ui">{SECTION_LABELS.references}</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {level.references.map((item) => (
                <ResourceLink key={item.label} item={item} compact />
              ))}
            </div>
          </section>
        ))}
      </div>

      <section className="surface mt-6 p-4 sm:p-5">
        <div className="eyebrow mb-1">學習路線</div>
        <h2 className="section-title mb-3">備考流程</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="surface-compact p-4">
            <div className="mb-1 text-meta font-semibold text-accent">01 選科目</div>
            <p className="text-ui leading-6 text-text-light">先確認級別與科目，再進科目總覽查看章節範圍。</p>
          </div>
          <div className="surface-compact p-4">
            <div className="mb-1 text-meta font-semibold text-accent">02 讀與練</div>
            <p className="text-ui leading-6 text-text-light">每章先讀主題式文章或學習指引，再用可用練習題檢查理解。</p>
          </div>
          <div className="surface-compact p-4">
            <div className="mb-1 text-meta font-semibold text-accent">03 做整卷</div>
            <p className="text-ui leading-6 text-text-light">最後用公告試題與樣題驗收，錯題再回到章節補強。</p>
          </div>
        </div>
      </section>
    </div>
  )
}
