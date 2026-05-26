import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import { loadSubjectQuestions } from '../data/questionLoaders'
import type { SubjectQuestions } from '../types'
import QuestionCard from '../components/practice/QuestionCard'

export default function PracticePage() {
  const { subjectId, chapterId, practiceSet } = useParams<{ subjectId: string; chapterId: string; practiceSet?: string }>()
  const isCodex100 = practiceSet === 'codex100'
  const isGuideExercise = practiceSet === 'guide'
  const [data, setData] = useState<SubjectQuestions | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const chapter = data?.chapters.find((c) => c.id === chapterId)
  const practiceSetSuffix = isCodex100 ? '/codex100' : isGuideExercise ? '/guide' : ''
  const chapterRoute = (targetChapterId: string) =>
    `/practice/${subjectId}/${targetChapterId}${practiceSetSuffix}`
  const level = resourceLevels.find((item) => item.subjects.some((subject) => subject.id === subjectId))
  const subject = level?.subjects.find((item) => item.id === subjectId)
  const subjectData = level?.toc.subjects.find((item) => item.id === subjectId)
  const summary = level && subjectId ? resourceSummary.levels[level.id].subjects[subjectId] : undefined
  const activeSummary = isCodex100 ? summary?.codex100 : isGuideExercise ? summary?.guide : summary?.ai
  const originalChapterCount = chapterId ? summary?.ai?.chapterCounts[chapterId] ?? 0 : 0
  const guideExerciseChapterCount = chapterId ? summary?.guide?.chapterCounts[chapterId] ?? 0 : 0
  const codex100ChapterCount = chapterId ? summary?.codex100?.chapterCounts[chapterId] ?? 0 : 0
  const setLabel = isCodex100 ? 'Codex 100 題' : isGuideExercise ? '學習指引練習' : 'AI 舊版練習'
  const selectableChapters = subjectData?.chapters.filter((item) => (activeSummary?.chapterCounts[item.id] ?? 0) > 0) ?? []

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [chapterId, practiceSet])

  useEffect(() => {
    let active = true
    setData(undefined)
    setLoadError(null)
    if (!subjectId) return

    setLoading(true)
    loadSubjectQuestions(subjectId, practiceSet)
      .then((loadedData) => {
        if (active) setData(loadedData)
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : String(error))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [subjectId, practiceSet])

  if (loading) {
    return <div className="page-shell text-text-light p-4">題目載入中...</div>
  }

  if (loadError) {
    return <div className="page-shell text-error p-4">題目載入失敗：{loadError}</div>
  }

  if (isGuideExercise && data && chapter && chapter.questions.length === 0) {
    return (
      <div className="page-shell">
        <div className="page-header mb-5">
          <div className="eyebrow mb-2">Practice</div>
          <h1 className="text-2xl font-bold text-primary mb-1">本章沒有學習指引練習題</h1>
          <div className="text-text-light">
          {data.subject} › {chapter.title} 在學習指引 PDF 內沒有內嵌章節練習題。
          </div>
        </div>
        {selectableChapters.length > 0 && (
          <div className="surface p-4 mb-5">
            <div className="section-title mb-2">可練習章節</div>
            <div className="flex flex-wrap gap-2">
              {selectableChapters.map((item) => (
                <Link
                  key={item.id}
                  to={`/practice/${subjectId}/${item.id}/guide`}
                  className="btn-warning"
                >
                  {item.title}（{summary?.guide?.chapterCounts[item.id] ?? 0} 題）
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (!data || (!isCodex100 && !isGuideExercise && subject?.practiceStatus === 'pending') || chapter?.questions.length === 0) {
    return (
      <div className="page-shell">
        <div className="page-header mb-5">
          <div className="eyebrow mb-2">Practice</div>
          <h1 className="text-2xl font-bold text-primary mb-1">章節練習題待建立</h1>
          <div className="text-text-light">
          {subject?.label ?? subjectId} 的 AI 模擬章節練習題尚未入庫。
          </div>
        </div>
        <div className="alert-warning mb-5">
          目前中級可先使用學習指引與公告試題；後續完成 AI 模擬題後，此入口會自動改為可練習。
        </div>
        <div className="flex flex-wrap gap-2">
          {subject?.guideTo && (
            <Link
              to={subject.guideTo}
              className="btn-outline"
            >
              前往學習指引
            </Link>
          )}
          {subject?.examTo && (
            <Link
              to={subject.examTo}
              className="btn-outline"
            >
              前往公告試題
            </Link>
          )}
        </div>
      </div>
    )
  }

  if (!chapter) {
    return <div className="page-shell text-error p-4">找不到章節：{chapterId}</div>
  }

  return (
    <div className="page-shell">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Practice</div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary mb-1">{chapter.title}</h1>
            <p className="text-[0.9rem] text-text-light">{data.subject} › {setLabel}</p>
          </div>
          <span className="pill">共 {chapter.questions.length} 題</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mb-5">
        {originalChapterCount > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}`}
            className={`btn-outline ${
              !isCodex100 && !isGuideExercise
                ? 'border-accent bg-accent text-white'
                : 'border-border text-text-light hover:border-accent hover:text-accent'
            }`}
          >
            AI 舊版練習（{originalChapterCount} 題）
          </Link>
        )}
        {guideExerciseChapterCount > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}/guide`}
            className={`btn-outline ${
              isGuideExercise
                ? 'border-[#9a5c17] bg-[#9a5c17] text-white'
                : 'border-border text-text-light hover:border-[#9a5c17] hover:text-[#9a5c17]'
            }`}
          >
            學習指引練習（{guideExerciseChapterCount} 題）
          </Link>
        )}
        {codex100ChapterCount > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}/codex100`}
            className={`btn-outline ${
              isCodex100
                ? 'border-[#5b7c2a] bg-[#5b7c2a] text-white'
                : 'border-border text-text-light hover:border-[#5b7c2a] hover:text-[#5b7c2a]'
            }`}
          >
            Codex 100 題（{codex100ChapterCount} 題）
          </Link>
        )}
      </div>
      {selectableChapters.length > 1 && (
        <div className="surface p-4 mb-5">
          <div className="section-title mb-2">切換章節</div>
          <div className="flex flex-wrap gap-2">
            {selectableChapters.map((item, index) => {
              const count = activeSummary?.chapterCounts[item.id] ?? 0
              return (
                <Link
                  key={item.id}
                  to={chapterRoute(item.id)}
                  className={`btn-outline ${
                    item.id === chapter.id
                      ? 'border-accent bg-accent text-white'
                      : 'border-border text-text-light hover:border-accent hover:text-accent'
                  }`}
                  title={item.title}
                >
                  {index + 1}. {item.title}（{count} 題）
                </Link>
              )
            })}
          </div>
        </div>
      )}
      <div>
        {chapter.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} index={i} />
        ))}
      </div>
    </div>
  )
}
