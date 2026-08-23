import { Link, useParams } from 'react-router-dom'
import type { ReactNode } from 'react'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import { articleMeta } from '../data/articleLoaders'
import type { GuideOutlinesData } from '../types'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'
import { PageHeader, StatePanel } from '../components/ui'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData

function resourceForSubject(subjectId?: string) {
  for (const level of resourceLevels) {
    const subject = level.subjects.find((item) => item.id === subjectId)
    const subjectData = level.toc.subjects.find((item) => item.id === subjectId)
    if (subject && subjectData) return { level, subject, subjectData }
  }
  const level = resourceLevels[0]
  return {
    level,
    subject: level.subjects[0],
    subjectData: level.toc.subjects[0],
  }
}

function ChapterMetric({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-md border border-border bg-[#f8fafc] px-2.5 py-1 text-[0.75rem] leading-5 text-text-light">
      <span className="font-semibold text-primary">{label}</span>
      <span className="ml-1">{value}</span>
    </span>
  )
}

function MutedAction({ children }: { children: ReactNode }) {
  return (
    <span className="btn-muted min-h-11 cursor-default">
      {children}
    </span>
  )
}

export default function SubjectOverviewPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const { level, subject, subjectData } = resourceForSubject(subjectId)
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
        eyebrow={level.label}
        title={subjectData.subject}
        description={`本科共 ${subjectData.chapters.length} 個章節；先選章節，再依序閱讀、練習，最後回到公告試題驗收。`}
        meta={
          <>
            <span className="pill">{subjectData.chapters.length} 章</span>
            <span className="pill pill-muted">{totalPracticeQuestions + totalGuideExerciseQuestions} 題可練習</span>
          </>
        }
        actions={subject.examTo && (
          <Link to={subject.examTo} className="btn-outline min-h-11">
            前往公告試題
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
            <div className="eyebrow mb-1">Chapters</div>
            <h2 className="section-title">章節路徑</h2>
          </div>
          <p className="text-[0.82rem] leading-6 text-text-light">
            每章依「先讀 → 練習」排序；題數與 PDF 頁碼整合在卡片中。
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {subjectData.chapters.map((ch, index) => {
            const pageRange = ch.page_range
              ? `PDF 第 ${ch.page_range[0] + 1}–${ch.page_range[1] + 1} 頁`
              : 'PDF 頁碼待補'
            const article = articleMeta(ch.id)
            const practiceCount = questionSummary?.chapterCounts[ch.id] ?? 0
            const guideExerciseCount = guideExerciseSummary?.chapterCounts[ch.id] ?? 0
            const hasChapterPractice = practiceCount > 0
            const hasGuideExercise = guideExerciseCount > 0
            const primaryRead = article
              ? { to: article.route, label: '讀主題文章' }
              : { to: `/guide/${subjectData.id}/${ch.id}`, label: '讀學習指引' }

            return (
              <article key={ch.id} className="surface p-4 sm:p-5">
                <div className="mb-3 flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-[0.82rem] font-bold tabular-nums text-white">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-[1rem] font-semibold leading-snug text-primary">{ch.title}</h3>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <ChapterMetric label="頁碼" value={pageRange} />
                      <ChapterMetric label="章節練習" value={hasChapterPractice ? `${practiceCount} 題` : '待建立'} />
                      <ChapterMetric label="指引練習" value={hasGuideExercise ? `${guideExerciseCount} 題` : '無內嵌題'} />
                    </div>
                  </div>
                </div>

                <div className="mb-4 flex flex-wrap gap-1.5">
                  {ch.subtopics.map((topic) => (
                    <span key={topic} className="pill pill-muted">{topic}</span>
                  ))}
                </div>

                <div className="rounded-lg border border-border bg-[#f8fafc] p-3">
                  <div className="mb-2 text-[0.78rem] font-semibold text-primary">先讀</div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                    <Link to={primaryRead.to} className="btn-primary min-h-11">
                      {primaryRead.label}
                    </Link>
                    {article && (
                      <Link to={`/guide/${subjectData.id}/${ch.id}`} className="btn-outline min-h-11">
                        學習指引
                      </Link>
                    )}
                  </div>

                  <div className="mb-2 mt-4 text-[0.78rem] font-semibold text-primary">再練習</div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                    {hasChapterPractice ? (
                      <Link to={`/practice/${subjectData.id}/${ch.id}`} className="btn-outline min-h-11">
                        章節練習（{practiceCount} 題）
                      </Link>
                    ) : (
                      <MutedAction>章節練習待建立</MutedAction>
                    )}
                    {hasGuideExercise ? (
                      <Link to={`/practice/${subjectData.id}/${ch.id}/guide`} className="btn-warning min-h-11">
                        學習指引練習（{guideExerciseCount} 題）
                      </Link>
                    ) : (
                      <MutedAction>無學習指引練習</MutedAction>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <details className="surface p-4 sm:p-5">
        <summary className="cursor-pointer text-[0.92rem] font-semibold text-primary">
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
