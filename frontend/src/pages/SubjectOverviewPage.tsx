import { Link, useParams } from 'react-router-dom'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import { articleMeta } from '../data/articleLoaders'
import type { GuideOutlinesData } from '../types'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'
import { PageHeader, StatePanel, subjectOptionById } from '../components/ui'
import { navLabel } from '../constants/navLabels'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
const MOBILE_SUBTOPICS = 4

function resourceForSubject(subjectId?: string) {
  for (const level of resourceLevels) {
    const subject = level.subjects.find((item) => item.id === subjectId)
    const subjectData = level.toc.subjects.find((item) => item.id === subjectId)
    if (subject && subjectData) return { level, subject, subjectData }
  }
  return undefined
}

function ChapterMetric({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-md border border-border bg-unanswered-soft px-2.5 py-1 text-caption leading-5 text-text-light">
      <span className="font-semibold text-primary">{label}</span>
      <span className="ml-1">{value}</span>
    </span>
  )
}

export default function SubjectOverviewPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const resource = resourceForSubject(subjectId)
  if (!resource) {
    return (
      <div className="page-shell">
        <PageHeader
          variant="plain"
          title="找不到科目"
          description={`科目代碼「${subjectId ?? ''}」不存在，或內容已經移動。`}
          actions={<Link to="/" className="btn-primary">回到首頁</Link>}
        />
      </div>
    )
  }
  const { level, subject, subjectData } = resource
  const guideOutline = guideOutlines.guides[subjectData.id]
  const hasPractice = subject.practiceStatus === 'available'
  const summary = resourceSummary.levels[level.id].subjects[subjectData.id]
  const questionSummary = summary?.ai
  const guideExerciseSummary = summary?.guide
  const totalPracticeQuestions = questionSummary?.total ?? 0
  const totalGuideExerciseQuestions = guideExerciseSummary?.total ?? 0

  return (
    <div className="page-shell">
      <PageHeader
        className="mb-5"
        eyebrow={navLabel('subject')}
        title={subjectOptionById(subjectData.id)?.fullLabel ?? subjectData.subject}
        description={`本科共 ${subjectData.chapters.length} 個章節；先選章節，再依序閱讀、練習，最後回到公告試題驗收。`}
        meta={
          <>
            <span className="pill">{subjectData.chapters.length} 章</span>
            <span className="pill pill-muted">{totalPracticeQuestions + totalGuideExerciseQuestions} 題可練習</span>
          </>
        }
        actions={subject.examTo && (
          <Link to={subject.examTo} className="btn-outline">
            前往{navLabel('exam')}
          </Link>
        )}
      />

      {!hasPractice && (
        <StatePanel tone="status" title="章節練習題尚未完整建立" className="mb-5">
          目前可先使用學習指引、學習指引練習與公告試題；有題目的章節會在下方卡片直接顯示入口。
        </StatePanel>
      )}

      <section className="mb-6">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="eyebrow mb-1">章節</div>
            <h2 className="section-title">章節路徑</h2>
          </div>
          <p className="text-meta leading-6 text-text-light">
            每章建議先讀，再練習；按鈕依建議順序排列。
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {subjectData.chapters.map((ch, index) => {
            const pageRange = ch.page_range
              ? `PDF 第 ${ch.page_range[0] + 1}–${ch.page_range[1] + 1} 頁`
              : null
            const article = articleMeta(ch.id)
            const practiceCount = questionSummary?.chapterCounts[ch.id] ?? 0
            const guideExerciseCount = guideExerciseSummary?.chapterCounts[ch.id] ?? 0
            const hasChapterPractice = practiceCount > 0
            const hasGuideExercise = guideExerciseCount > 0
            const guideRoute = `/guide/${subjectData.id}/${ch.id}`
            // 建議順序：先讀（文章或學習指引）→ 再練習；沒有入口的項目只留一行淡色說明，不畫成按鈕
            const actions: { to: string; label: string; className: string }[] = [
              article
                ? { to: article.route, label: `讀${navLabel('articles')}`, className: 'btn-primary' }
                : { to: guideRoute, label: '讀學習指引', className: 'btn-primary' },
            ]
            if (article) actions.push({ to: guideRoute, label: '學習指引', className: 'btn-outline' })
            if (hasChapterPractice) {
              actions.push({
                to: `/practice/${subjectData.id}/${ch.id}`,
                label: `${navLabel('practice')}（${practiceCount} 題）`,
                className: 'btn-outline',
              })
            }
            if (hasGuideExercise) {
              actions.push({
                to: `/practice/${subjectData.id}/${ch.id}/guide`,
                label: `${navLabel('guidePractice')}（${guideExerciseCount} 題）`,
                className: 'btn-outline',
              })
            }
            const unavailable = [
              !hasChapterPractice && `${navLabel('practice')}待建立`,
              !hasGuideExercise && `本章無${navLabel('guidePractice')}`,
            ].filter((note): note is string => Boolean(note))

            return (
              <article key={ch.id} className="surface p-4 sm:p-5">
                <div className="mb-3 flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-meta font-bold tabular-nums text-white">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-reading font-semibold leading-snug text-primary">{ch.title}</h3>
                    {pageRange && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <ChapterMetric label="頁碼" value={pageRange} />
                      </div>
                    )}
                  </div>
                </div>

                <div className="mb-4 flex flex-wrap gap-1.5">
                  {/* 手機只列前幾個主題，避免一章就超過一個畫面 */}
                  {ch.subtopics.map((topic, topicIndex) => (
                    <span
                      key={topic}
                      className={`pill pill-muted ${topicIndex >= MOBILE_SUBTOPICS ? 'max-sm:hidden' : ''}`}
                    >
                      {topic}
                    </span>
                  ))}
                  {ch.subtopics.length > MOBILE_SUBTOPICS && (
                    <span className="pill pill-muted sm:hidden">
                      另 {ch.subtopics.length - MOBILE_SUBTOPICS} 個主題
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                  {actions.map((action, actionIndex) => (
                    <Link
                      key={action.to}
                      to={action.to}
                      className={`${action.className} text-center ${
                        actions.length % 2 === 1 && actionIndex === 0 ? 'col-span-2' : ''
                      }`}
                    >
                      {action.label}
                    </Link>
                  ))}
                </div>
                {unavailable.length > 0 && (
                  <p className="mt-2 text-meta leading-6 text-text-light">{unavailable.join('；')}</p>
                )}
              </article>
            )
          })}
        </div>
      </section>

      <details className="surface p-4 sm:p-5">
        <summary className="cursor-pointer py-2.5 text-body font-semibold text-primary">
          學習指引完整 PDF 目錄
        </summary>
        <div className="mt-4">
          {guideOutline ? (
            <GuideOutlineTree
              subjectId={subjectData.id}
              rootIds={guideOutline.root}
              nodesById={guideOutline.nodesById}
            />
          ) : (
            <StatePanel tone="empty">目前沒有可顯示的學習指引目錄。</StatePanel>
          )}
        </div>
      </details>
    </div>
  )
}
