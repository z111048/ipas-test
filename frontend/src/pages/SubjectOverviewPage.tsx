import { Link, useParams } from 'react-router-dom'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import type { GuideOutlinesData } from '../types'
import ProgressBar from '../components/shared/ProgressBar'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'

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

export default function SubjectOverviewPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const { level, subject, subjectData } = resourceForSubject(subjectId)
  const guideOutline = guideOutlines.guides[subjectData.id]
  const hasPractice = subject.practiceStatus === 'available'
  const summary = resourceSummary.levels[level.id].subjects[subjectData.id]
  const questionSummary = summary?.ai
  const guideExerciseSummary = summary?.guide
  const codex100Summary = summary?.codex100
  const practiceCounts = subjectData.chapters.map((chapter) =>
    questionSummary?.chapterCounts[chapter.id] ?? 0
  )
  const guideExerciseCounts = subjectData.chapters.map((chapter) =>
    guideExerciseSummary?.chapterCounts[chapter.id] ?? 0
  )
  const codex100Counts = subjectData.chapters.map((chapter) =>
    codex100Summary?.chapterCounts[chapter.id] ?? 0
  )
  const maxPracticeQ = Math.max(...practiceCounts, 1)
  const maxGuideExerciseQ = Math.max(...guideExerciseCounts, 1)
  const maxCodex100Q = Math.max(...codex100Counts, 1)

  return (
    <div>
      <div className="text-[0.78rem] font-semibold text-accent mb-1">{level.label}</div>
      <div className="text-2xl font-bold text-primary mb-1">{subjectData.subject}</div>
      <div className="text-text-light mb-5">
        評鑑主題：{subjectData.chapters.map((c) => c.title).join(' / ')}
      </div>

      {!hasPractice && (
        <div className="rounded-lg border border-[#f2d28b] bg-[#fff8e6] text-[#7a5700] px-4 py-3 mb-5 text-[0.9rem]">
          章節練習題尚未建立；目前可先使用學習指引與公告試題，完成 AI 模擬題後此區會自動顯示題數。
        </div>
      )}

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-6">
        <h2 className="text-lg font-semibold text-primary mb-4">學習指引完整 PDF 目錄</h2>
        {guideOutline && (
          <GuideOutlineTree
            subjectId={subjectData.id}
            rootIds={guideOutline.root}
            nodesById={guideOutline.nodesById}
          />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {subjectData.chapters.map((ch) => {
          const pageRange = ch.page_range
            ? `PDF 第 ${ch.page_range[0] + 1}–${ch.page_range[1] + 1} 頁`
            : null
          return (
            <div key={ch.id} className="bg-card rounded-xl shadow-sm border border-border p-5">
              <h3 className="text-primary font-semibold mb-1">{ch.title}</h3>
              {pageRange && (
                <div className="text-[0.75rem] text-text-light mb-3">{pageRange}</div>
              )}
              <div className="flex flex-wrap gap-1 mb-4">
                {ch.subtopics.map((t) => (
                  <span key={t} className="text-[0.75rem] bg-[#eef5ff] text-accent px-2 py-0.5 rounded-full">{t}</span>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/guide/${subjectData.id}/${ch.id}`}
                  className="text-[0.8rem] px-3 py-1 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
                >
                  學習指引
                </Link>
                {hasPractice ? (
                  <Link
                    to={`/practice/${subjectData.id}/${ch.id}`}
                    className="text-[0.8rem] px-3 py-1 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
                  >
                    AI 舊版練習
                  </Link>
                ) : (
                  <span className="text-[0.8rem] px-3 py-1 rounded-lg border border-border text-text-light bg-[#f5f7fa]">
                    練習題待建立
                  </span>
                )}
                {guideExerciseCounts[subjectData.chapters.findIndex((item) => item.id === ch.id)] > 0 && (
                  <Link
                    to={`/practice/${subjectData.id}/${ch.id}/guide`}
                    className="text-[0.8rem] px-3 py-1 rounded-lg border border-[#9a5c17] text-[#9a5c17] hover:bg-[#9a5c17] hover:text-white transition-colors no-underline"
                  >
                    學習指引練習
                  </Link>
                )}
                {codex100Counts[subjectData.chapters.findIndex((item) => item.id === ch.id)] > 0 && (
                  <Link
                    to={`/practice/${subjectData.id}/${ch.id}/codex100`}
                    className="text-[0.8rem] px-3 py-1 rounded-lg border border-[#5b7c2a] text-[#5b7c2a] hover:bg-[#5b7c2a] hover:text-white transition-colors no-underline"
                  >
                    Codex 100 題
                  </Link>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-6">
        <h2 className="text-lg font-semibold text-primary mb-4">AI 章節練習（舊版）狀態</h2>
        <div className="space-y-3">
          {subjectData.chapters.map((ch, index) => {
            const n = practiceCounts[index]
            return (
              <div key={ch.id}>
                <div className="flex justify-between text-[0.85rem] mb-1">
                  <span>{ch.title}</span>
                  <span className="text-accent font-semibold">{hasPractice ? `${n} 題` : '待建立'}</span>
                </div>
                <ProgressBar percent={hasPractice ? (n / maxPracticeQ) * 100 : 0} />
              </div>
            )
          })}
        </div>
      </div>

      {guideExerciseSummary && (
        <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-6">
          <h2 className="text-lg font-semibold text-primary mb-4">學習指引練習狀態</h2>
          <div className="space-y-3">
            {subjectData.chapters.map((ch, index) => {
              const n = guideExerciseCounts[index]
              return (
                <div key={ch.id}>
                  <div className="flex justify-between text-[0.85rem] mb-1">
                    <span>{ch.title}</span>
                    <span className="text-[#9a5c17] font-semibold">{n > 0 ? `${n} 題` : '無內嵌題'}</span>
                  </div>
                  <ProgressBar percent={n > 0 ? (n / maxGuideExerciseQ) * 100 : 0} />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {codex100Summary && (
        <div className="bg-card rounded-xl shadow-sm border border-border p-5">
          <h2 className="text-lg font-semibold text-primary mb-4">Codex 100 題狀態</h2>
          <div className="space-y-3">
            {subjectData.chapters.map((ch, index) => {
              const n = codex100Counts[index]
              return (
                <div key={ch.id}>
                  <div className="flex justify-between text-[0.85rem] mb-1">
                    <span>{ch.title}</span>
                    <span className="text-[#5b7c2a] font-semibold">{n > 0 ? `${n} 題` : '待建立'}</span>
                  </div>
                  <ProgressBar percent={n > 0 ? (n / maxCodex100Q) * 100 : 0} />
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
