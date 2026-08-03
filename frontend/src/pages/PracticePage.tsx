import { Link, useParams } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import { loadSubjectQuestions } from '../data/questionLoaders'
import type { SubjectQuestions } from '../types'
import QuestionCard from '../components/practice/QuestionCard'

type AnswerMap = Record<string, 'A' | 'B' | 'C' | 'D'>

function practiceStorageKey(subjectId?: string, chapterId?: string, practiceSet?: string) {
  return `ipas:practice:${subjectId ?? ''}:${chapterId ?? ''}:${practiceSet ?? 'chapter'}`
}

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'TEXTAREA') return true
  if (tag === 'INPUT') {
    const type = (target as HTMLInputElement).type
    return type !== 'radio' && type !== 'checkbox'
  }
  return target.isContentEditable
}

export default function PracticePage() {
  const { subjectId, chapterId, practiceSet } = useParams<{ subjectId: string; chapterId: string; practiceSet?: string }>()
  const isCodex100 = practiceSet === 'codex100'
  const isGuideExercise = practiceSet === 'guide'
  const [data, setData] = useState<SubjectQuestions | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [answers, setAnswers] = useState<AnswerMap>({})
  const [activeIndex, setActiveIndex] = useState(0)
  const [showRestoreBanner, setShowRestoreBanner] = useState(false)
  const questionRefs = useRef<Array<HTMLElement | null>>([])
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
  const setLabel = isCodex100 ? '精選 100 題' : isGuideExercise ? '學習指引練習' : '章節練習'
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

  // 進度還原：切換章節/題組時，讀取 localStorage 中的作答紀錄
  useEffect(() => {
    setActiveIndex(0)
    questionRefs.current = []
    if (!subjectId || !chapterId) {
      setAnswers({})
      setShowRestoreBanner(false)
      return
    }
    const key = practiceStorageKey(subjectId, chapterId, practiceSet)
    try {
      const raw = window.localStorage.getItem(key)
      if (raw) {
        const parsed = JSON.parse(raw) as AnswerMap
        if (parsed && Object.keys(parsed).length > 0) {
          setAnswers(parsed)
          setShowRestoreBanner(true)
          return
        }
      }
    } catch {
      // localStorage 不可用（例如無痕模式）時忽略
    }
    setAnswers({})
    setShowRestoreBanner(false)
  }, [subjectId, chapterId, practiceSet])

  // 進度保存：作答狀態變更時寫回 localStorage
  useEffect(() => {
    if (!subjectId || !chapterId) return
    const key = practiceStorageKey(subjectId, chapterId, practiceSet)
    try {
      if (Object.keys(answers).length > 0) {
        window.localStorage.setItem(key, JSON.stringify(answers))
      } else {
        window.localStorage.removeItem(key)
      }
    } catch {
      // 忽略儲存失敗（例如容量已滿）
    }
  }, [answers, subjectId, chapterId, practiceSet])

  const goTo = (idx: number) => {
    const total = chapter?.questions.length ?? 0
    if (total === 0) return
    const clamped = Math.max(0, Math.min(idx, total - 1))
    setActiveIndex(clamped)
    questionRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const handleRestart = () => {
    setAnswers({})
    setShowRestoreBanner(false)
    goTo(0)
    if (subjectId && chapterId) {
      try {
        window.localStorage.removeItem(practiceStorageKey(subjectId, chapterId, practiceSet))
      } catch {
        // ignore
      }
    }
  }

  // 鍵盤操作：1-4 選答，←/→ 切換上下題
  useEffect(() => {
    if (!chapter || chapter.questions.length === 0) return
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return
      if (['1', '2', '3', '4'].includes(event.key)) {
        const q = chapter.questions[activeIndex]
        if (q && !answers[q.id]) {
          const optKey = (['A', 'B', 'C', 'D'] as const)[Number(event.key) - 1]
          setAnswers((prev) => ({ ...prev, [q.id]: optKey }))
        }
        event.preventDefault()
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        goTo(activeIndex + 1)
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        goTo(activeIndex - 1)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [chapter, activeIndex, answers])

  // 捲動時追蹤目前題號（供鍵盤切題與行動裝置底部列使用）
  useEffect(() => {
    if (!chapter || chapter.questions.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const closest = visible.reduce((a, b) => (a.intersectionRatio > b.intersectionRatio ? a : b))
        const idx = Number((closest.target as HTMLElement).dataset.qIndex)
        if (!Number.isNaN(idx)) setActiveIndex(idx)
      },
      { threshold: [0.3, 0.6, 0.9], rootMargin: '-96px 0px -35% 0px' },
    )
    questionRefs.current.forEach((el) => el && observer.observe(el))
    return () => observer.disconnect()
  }, [chapter])

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
          {subject?.label ?? subjectId} 的章節練習題尚未入庫。
          </div>
        </div>
        <div className="alert-warning mb-5">
          目前中級可先使用學習指引與公告試題；章節練習題建置後，此入口會自動改為可練習。
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
    <div className="page-shell pb-24 sm:pb-4">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Practice</div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary mb-1">{chapter.title}</h1>
            <p className="text-[0.9rem] text-text-light">{data.subject} › {setLabel}</p>
          </div>
          <span className="pill">共 {chapter.questions.length} 題</span>
        </div>
        <p className="mt-2 text-[0.72rem] text-text-light">鍵盤：1–4 選答，←→ 切換上下題</p>
      </div>
      {showRestoreBanner && (
        <div className="alert-warning mb-5 flex flex-wrap items-center justify-between gap-3">
          <span>已為您自動恢復上次的練習進度。</span>
          <button className="btn-outline shrink-0" onClick={handleRestart}>
            重新開始
          </button>
        </div>
      )}
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
            章節練習（{originalChapterCount} 題）
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
            精選 100 題（{codex100ChapterCount} 題）
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
          <QuestionCard
            key={q.id}
            question={q}
            index={i}
            selected={answers[q.id] ?? null}
            onSelect={(key) => setAnswers((prev) => ({ ...prev, [q.id]: key }))}
            isActive={i === activeIndex}
            registerRef={(el) => {
              questionRefs.current[i] = el
            }}
          />
        ))}
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-between gap-2 border-t border-border bg-white/95 px-4 py-3 shadow-[0_-2px_10px_rgba(0,0,0,0.08)] backdrop-blur sm:hidden">
        <button
          className="btn-outline flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex - 1)}
          disabled={activeIndex === 0}
        >
          ← 上一題
        </button>
        <span className="shrink-0 whitespace-nowrap text-[0.78rem] text-text-light">
          {activeIndex + 1} / {chapter.questions.length}
        </span>
        <button
          className="btn-outline flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex + 1)}
          disabled={activeIndex === chapter.questions.length - 1}
        >
          下一題 →
        </button>
      </div>
    </div>
  )
}
