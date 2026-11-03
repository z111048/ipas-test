import { Link } from 'react-router-dom'
import {
  resourceLevels,
  resourceStats,
  resourceSummary,
  type LevelResource,
  type ResourceNavItem,
  type SubjectResource,
} from '../data/resourceRegistry'
import { learningArticleIndex } from '../data/articleLoaders'
import { examsForLevel } from '../data/resourceCatalog'
import StatBox from '../components/shared/StatBox'
import { PageHeader, subjectOptionById } from '../components/ui'
import { SECTION_LABELS, SITE_NAME, navLabel } from '../constants/navLabels'
import { SeasonalCompanion, SeasonalHeroDecor, SeasonalScrollFlyer } from '../features/seasonal'

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

  const className = `group block min-h-11 panel-muted no-underline transition-colors hover:bg-accent-soft ${
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
      <div className={`rounded-xl border border-dashed border-border-strong ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
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
      <div className="rounded-lg border border-dashed border-border-strong px-2.5 py-2.5 text-ui sm:px-3 text-text-light">
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
          ? 'border-accent bg-accent text-white shadow-sm hover:border-accent-hover hover:bg-accent-hover'
          : 'border-transparent bg-white text-primary shadow-[0_1px_2px_rgba(15,23,42,0.05)] hover:bg-accent-soft hover:text-accent-hover'
      }`}
    >
      <span className="block font-semibold">{label}</span>
      <span className={`mt-0.5 block text-caption leading-5 ${primary ? 'text-white/85' : 'text-text-light'}`}>
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

/**
 * 每級只列最新一次的公告試題（每科一份），其餘與樣題收進「查看全部公告試題」。
 * 「最新」取自 resource catalog 的排序：同一科目第一份 official 就是最新一次。
 */
function LatestExams({ level }: { level: LevelResource }) {
  const officials = examsForLevel(level.id).filter((exam) => exam.kind === 'official')
  const seen = new Set<string | null>()
  const latestIndexes = officials.flatMap((exam, index) => {
    if (seen.has(exam.subjectId)) return []
    seen.add(exam.subjectId)
    return [index]
  })
  const latest = latestIndexes.map((index) => level.exams[index]).filter(Boolean)
  const others = [
    ...level.exams.filter((_, index) => !latestIndexes.includes(index)),
    ...level.samples,
  ]

  return (
    <div className="mb-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {latest.map((item) => (
          <ResourceLink key={item.label} item={item} compact />
        ))}
      </div>
      {others.length > 0 && (
        <details className="group mt-3">
          <summary className="flex min-h-11 cursor-pointer items-center gap-1 text-ui font-semibold text-accent hover:text-accent-hover">
            <span aria-hidden="true" className="inline-block transition-transform group-open:rotate-90">▸</span>
            查看全部{SECTION_LABELS.exams}（另 {others.length} 份{level.samples.length > 0 ? '，含樣題' : ''}）
          </summary>
          <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
            {others.map((item) => (
              <ResourceLink key={item.label} item={item} compact />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

export default function HomePage() {
  const totalPractice = resourceStats.junior.practiceQuestions + resourceStats.middle.practiceQuestions
  const totalOfficial = resourceStats.junior.officialQuestions + resourceStats.middle.officialQuestions
  const totalVisuals = resourceSummary.visuals?.total ?? 0
  const firstArticleTo = learningArticleIndex.articlesById[learningArticleIndex.flatArticleIds[0]]?.route ?? '/articles'
  const firstExamTo = resourceLevels[0].exams[0]?.to
  // 捲動容器是 <main id="main-content">；scrollIntoView 會捲動最近的可捲動祖先（main），
  // 再把焦點移到區塊標題，鍵盤與螢幕閱讀器使用者也會落在同一處。
  const goToSubjects = () => {
    const section = document.getElementById('choose-subject')
    if (!section) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    section.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
    document.getElementById('choose-subject-title')?.focus({ preventScroll: true })
  }

  return (
    <div className="page-shell">
      <PageHeader
        variant="hero"
        // 手機（390×844）要讓第一張科目卡完整落在第一屏：hero 上下內距與間距收緊一點。
        className="mb-3 max-sm:py-4 sm:mb-5"
        eyebrow={
          <>
            <span className="hero-chip">經濟部 iPAS 產業人才能力鑑定</span>
            <span className="hero-chip">初級・中級</span>
          </>
        }
        title={SITE_NAME}
        decor={<SeasonalHeroDecor />}
        description="先選級別與科目，再依章節讀指引、做練習、驗收公告試題。"
        actions={
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <button
              type="button"
              className="btn-hero col-span-2"
              onClick={goToSubjects}
            >
              選擇級別與科目
            </button>
            <Link to={firstArticleTo} className="btn-hero-ghost">{navLabel('articles')}</Link>
            {firstExamTo && <Link to={firstExamTo} className="btn-hero-ghost">{navLabel('exam')}</Link>}
          </div>
        }
        asideClassName="hidden sm:block"
        aside={
          <div className="grid grid-cols-3 gap-3 border-t border-indigo-100 pt-4 text-primary lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{resourceStats.junior.subjects + resourceStats.middle.subjects}</div>
              <div className="mt-1 text-caption font-medium text-text-light">科目</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalPractice}</div>
              <div className="mt-1 text-caption font-medium text-text-light">練習題</div>
            </div>
            <div>
              <div className="text-[1.35rem] font-black leading-none tabular-nums">{totalOfficial}</div>
              <div className="mt-1 text-caption font-medium text-text-light">{navLabel('exam')}題數</div>
            </div>
          </div>
        }
      />

      <section id="choose-subject" className="surface mb-6 p-3 sm:p-5 scroll-mt-4">
        <div className="mb-2 flex flex-col gap-2 sm:mb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="eyebrow mb-1 hidden sm:block">從這裡開始</div>
            <h2 id="choose-subject-title" tabIndex={-1} className="section-title focus:outline-none">選擇級別與科目</h2>
          </div>
          <div className="hidden text-meta leading-6 text-text-light sm:block">
            每科都可從學習指引、練習與公告試題進入；尚未建置的資源會顯示狀態。
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {resourceLevels.map((level) => {
            const stats = resourceStats[level.id]
            return (
              <section key={level.id} className="sm:p-1">
                <div className="mb-2 flex flex-wrap items-start justify-between gap-3 sm:mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-primary">{level.label}</h3>
                    {/* 手機省略副標，讓第一張科目卡完整出現在第一屏。 */}
                    <p className="mt-1 hidden text-ui leading-6 text-text-light sm:block">{level.subtitle}</p>
                  </div>
                  <span className="pill shrink-0">{stats.subjects} 科 / {stats.chapters} 章</span>
                </div>
                <div className="space-y-3">
                  {level.subjects.map((subject) => {
                    const practice = practiceTarget(subject)
                    return (
                      <article key={subject.id} className="panel-muted p-3 sm:p-4">
                        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 sm:mb-3">
                          <Link to={subject.overviewTo ?? subject.guideTo ?? '/'} className="text-link text-primary hover:text-accent">
                            {subjectOptionById(subject.id)?.fullLabel ?? subject.label}
                          </Link>
                          <span className="text-meta text-text-light">
                            {subject.chapters} 個章節
                          </span>
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
            <h3 className="section-title mb-2 text-ui">最新{SECTION_LABELS.exams}</h3>
            <LatestExams level={level} />
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
        <SeasonalCompanion className="absolute right-2 top-2" />
        <div className="eyebrow mb-1">學習路線</div>
        <h2 className="section-title mb-3">備考流程</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="panel-muted p-4">
            <div className="mb-1 text-meta font-semibold text-accent">01 選科目</div>
            <p className="text-ui leading-6 text-text-light">先確認級別與科目，再進科目總覽查看章節範圍。</p>
          </div>
          <div className="panel-muted p-4">
            <div className="mb-1 text-meta font-semibold text-accent">02 讀與練</div>
            <p className="text-ui leading-6 text-text-light">每章先讀主題式文章或學習指引，再用可用練習題檢查理解。</p>
          </div>
          <div className="panel-muted p-4">
            <div className="mb-1 text-meta font-semibold text-accent">03 做整卷</div>
            <p className="text-ui leading-6 text-text-light">最後用公告試題與樣題驗收，錯題再回到章節補強。</p>
          </div>
        </div>
      </section>
      <SeasonalScrollFlyer />
    </div>
  )
}
