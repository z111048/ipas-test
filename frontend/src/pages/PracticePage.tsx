import { Link, useSearchParams, useParams } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { MobileActionBar, PageHeader, StatePanel } from '../components/ui'
import QuestionCard from '../components/practice/QuestionCard'
import { resourceLevels, resourceSummary } from '../data/resourceRegistry'
import { loadSubjectQuestions } from '../data/questionLoaders'
import type { Question, SubjectQuestions } from '../types'
import { preferredScrollBehavior } from '../utils/motion'

type AnswerMap = Record<string, 'A' | 'B' | 'C' | 'D'>
type QuestionStatus = 'pending' | 'correct' | 'wrong'

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

function questionStatus(question: Question, answer: 'A' | 'B' | 'C' | 'D' | null): QuestionStatus {
  if (!answer) return 'pending'
  return answer === question.answer ? 'correct' : 'wrong'
}

function statusLabel(status: QuestionStatus) {
  if (status === 'correct') return '答對'
  if (status === 'wrong') return '答錯'
  return '待答'
}

function statusClass(status: QuestionStatus, active: boolean) {
  const activeClass = active ? 'ring-2 ring-accent/40 ring-offset-2' : ''
  if (status === 'correct') {
    return `border-success/35 bg-[#ecfdf3] text-success ${activeClass}`
  }
  if (status === 'wrong') {
    return `border-error/30 bg-[#fdf2f2] text-error ${activeClass}`
  }
  return `border-border bg-white text-text-light ${activeClass}`
}

export default function PracticePage() {
  const { subjectId, chapterId, practiceSet } = useParams<{ subjectId: string; chapterId: string; practiceSet?: string }>()
  const isGuideExercise = practiceSet === 'guide'
  const [data, setData] = useState<SubjectQuestions | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [answers, setAnswers] = useState<AnswerMap>({})
  const [activeIndex, setActiveIndex] = useState(0)
  const [showRestoreBanner, setShowRestoreBanner] = useState(false)
  const [showQuestionNav, setShowQuestionNav] = useState(true)
  const questionRefs = useRef<Array<HTMLElement | null>>([])
  const [searchParams] = useSearchParams()
  const targetQuestionId = searchParams.get('q')
  const chapter = data?.chapters.find((c) => c.id === chapterId)
  const practiceSetSuffix = isGuideExercise ? '/guide' : ''
  const chapterRoute = (targetChapterId: string) => `/practice/${subjectId}/${targetChapterId}${practiceSetSuffix}`
  const level = resourceLevels.find((item) => item.subjects.some((subject) => subject.id === subjectId))
  const subject = level?.subjects.find((item) => item.id === subjectId)
  const subjectData = level?.toc.subjects.find((item) => item.id === subjectId)
  const summary = level && subjectId ? resourceSummary.levels[level.id].subjects[subjectId] : undefined
  const activeSummary = isGuideExercise ? summary?.guide : summary?.ai
  const originalChapterCount = chapterId ? summary?.ai?.chapterCounts[chapterId] ?? 0 : 0
  const guideExerciseChapterCount = chapterId ? summary?.guide?.chapterCounts[chapterId] ?? 0 : 0
  const setLabel = isGuideExercise ? '學習指引練習' : '章節練習'
  const selectableChapters = subjectData?.chapters.filter((item) => (activeSummary?.chapterCounts[item.id] ?? 0) > 0) ?? []

  useEffect(() => {
    if (targetQuestionId) return
    window.scrollTo(0, 0)
  }, [chapterId, practiceSet, targetQuestionId])

  useEffect(() => {
    if (!targetQuestionId || !chapter) return
    const index = chapter.questions.findIndex((q) => q.id === targetQuestionId)
    if (index < 0) return
    setActiveIndex(index)
    const timer = window.setTimeout(() => {
      questionRefs.current[index]?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'center' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [targetQuestionId, chapter])

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

  useEffect(() => {
    setActiveIndex(0)
    questionRefs.current = []
    setShowQuestionNav(true)
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
    questionRefs.current[clamped]?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'center' })
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
        <PageHeader
          className="mb-5"
          eyebrow="Practice"
          title="本章沒有學習指引練習題"
          description={`${data.subject} › ${chapter.title} 在學習指引 PDF 內沒有內嵌章節練習題。`}
        />
        {selectableChapters.length > 0 && (
          <StatePanel
            title="可練習章節"
            className="mb-5"
            action={selectableChapters.map((item) => (
              <Link
                key={item.id}
                to={`/practice/${subjectId}/${item.id}/guide`}
                className="btn-warning min-h-[44px]"
              >
                {item.title}（{summary?.guide?.chapterCounts[item.id] ?? 0} 題）
              </Link>
            ))}
          >
            可直接改做有題目的章節，不需要回上一頁。
          </StatePanel>
        )}
      </div>
    )
  }

  if (!data || (!isGuideExercise && subject?.practiceStatus === 'pending') || chapter?.questions.length === 0) {
    return (
      <div className="page-shell">
        <PageHeader
          className="mb-5"
          eyebrow="Practice"
          title="章節練習題待建立"
          description={`${subject?.label ?? subjectId} 的章節練習題尚未入庫。`}
        />
        <StatePanel
          tone="status"
          className="mb-5"
          action={
            <>
              {subject?.guideTo && (
                <Link to={subject.guideTo} className="btn-outline min-h-[44px]">
                  前往學習指引
                </Link>
              )}
              {subject?.examTo && (
                <Link to={subject.examTo} className="btn-outline min-h-[44px]">
                  前往公告試題
                </Link>
              )}
            </>
          }
        >
          目前中級可先使用學習指引與公告試題；章節練習題建置後，此入口會自動改為可練習。
        </StatePanel>
      </div>
    )
  }

  if (!chapter) {
    return <div className="page-shell text-error p-4">找不到章節：{chapterId}</div>
  }

  const statuses = chapter.questions.map((question) => questionStatus(question, answers[question.id] ?? null))
  const answeredCount = statuses.filter((status) => status !== 'pending').length
  const correctCount = statuses.filter((status) => status === 'correct').length
  const wrongCount = statuses.filter((status) => status === 'wrong').length
  const pendingCount = chapter.questions.length - answeredCount
  const completed = pendingCount === 0
  const chapterIndex = selectableChapters.findIndex((item) => item.id === chapter.id)
  const nextChapter = chapterIndex >= 0 ? selectableChapters[chapterIndex + 1] : undefined
  const firstWrongIndex = statuses.findIndex((status) => status === 'wrong')
  const firstPendingIndex = statuses.findIndex((status) => status === 'pending')
  const currentStatus = statuses[activeIndex] ?? 'pending'

  const handleRedoWrong = () => {
    const retainedAnswers = chapter.questions.reduce<AnswerMap>((next, question) => {
      const answer = answers[question.id]
      if (answer === question.answer) next[question.id] = answer
      return next
    }, {})
    setAnswers(retainedAnswers)
    setShowRestoreBanner(false)
    const nextIndex = firstWrongIndex >= 0 ? firstWrongIndex : 0
    window.setTimeout(() => goTo(nextIndex), 0)
  }

  const activeQuestionNavLabel = currentStatus === 'correct'
    ? '目前題已答對'
    : currentStatus === 'wrong'
      ? '目前題需複習'
      : '目前題尚未作答'

  return (
    <div className="page-shell pb-28 sm:pb-6">
      <PageHeader
        className="mb-4"
        eyebrow="Practice"
        title={chapter.title}
        description={
          <>
            <span>{data.subject} › {setLabel}</span>
            <span className="block text-[0.78rem] text-text-light mt-1">
              鍵盤：1–4 選答，←→ 切換上下題
            </span>
          </>
        }
        meta={
          <>
            <span className="pill">共 {chapter.questions.length} 題</span>
            <span className="pill pill-muted">已答 {answeredCount}</span>
          </>
        }
        actions={(
          <button className="btn-outline min-h-[44px]" onClick={handleRestart}>
            重新開始
          </button>
        )}
      />

      {showRestoreBanner && (
        <StatePanel
          className="mb-4"
          title="已恢復上次進度"
          action={(
            <button className="btn-outline min-h-[44px]" onClick={handleRestart}>
              重新開始
            </button>
          )}
        >
          你上次已作答 {answeredCount} / {chapter.questions.length} 題，可以直接從目前題號繼續。
        </StatePanel>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {originalChapterCount > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}`}
            className={`btn-outline min-h-[44px] ${
              !isGuideExercise
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
            className={`btn-outline min-h-[44px] ${
              isGuideExercise
                ? 'border-[#9a5c17] bg-[#9a5c17] text-white'
                : 'border-border text-text-light hover:border-[#9a5c17] hover:text-[#9a5c17]'
            }`}
          >
            學習指引練習（{guideExerciseChapterCount} 題）
          </Link>
        )}
      </div>

      {completed && (
        <StatePanel
          className="mb-4"
          title="本章練習完成"
          action={(
            <>
              <button className="btn-outline min-h-[44px]" onClick={wrongCount > 0 ? handleRedoWrong : handleRestart}>
                {wrongCount > 0 ? '重做錯題' : '重新練習'}
              </button>
              {subject?.overviewTo && (
                <Link to={subject.overviewTo} className="btn-outline min-h-[44px]">
                  回科目總覽
                </Link>
              )}
              {nextChapter && (
                <Link to={chapterRoute(nextChapter.id)} className="btn-primary min-h-[44px]">
                  下一章
                </Link>
              )}
            </>
          )}
        >
          已答 {answeredCount} 題，答對 {correctCount} 題，待複習 {wrongCount} 題。
          {wrongCount > 0 ? ' 建議先重做錯題，再前往下一章。' : ' 這一章可以直接往下走。'}
        </StatePanel>
      )}

      <section className="surface mb-4 p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="section-title">作答進度</div>
            <div className="mt-2 flex flex-wrap gap-2 text-[0.78rem]">
              <span className="rounded-full border border-border bg-white px-3 py-1.5 text-app-text">已答 {answeredCount}</span>
              <span className="rounded-full border border-success/25 bg-[#ecfdf3] px-3 py-1.5 text-success">答對 {correctCount}</span>
              <span className="rounded-full border border-error/20 bg-[#fdf2f2] px-3 py-1.5 text-error">待複習 {wrongCount}</span>
              <span className="rounded-full border border-[#d7e7f5] bg-[#f4f9fd] px-3 py-1.5 text-app-text">待完成 {pendingCount}</span>
            </div>
          </div>
          <button
            type="button"
            className="btn-outline min-h-[44px] shrink-0"
            onClick={() => setShowQuestionNav((open) => !open)}
            aria-expanded={showQuestionNav}
          >
            {showQuestionNav ? '收起題號導航' : '展開題號導航'}
          </button>
        </div>

        {showQuestionNav && (
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between gap-3 text-[0.8rem] text-text-light">
              <span>目前題號：第 {activeIndex + 1} 題</span>
              {pendingCount > 0 && firstPendingIndex >= 0 && (
                <button
                  type="button"
                  className="btn-outline min-h-[44px] text-[0.8rem]"
                  onClick={() => goTo(firstPendingIndex)}
                >
                  跳到未答題
                </button>
              )}
            </div>
            <div className="grid grid-cols-5 gap-2 sm:grid-cols-6 lg:grid-cols-8">
              {chapter.questions.map((question, index) => {
                const status = statuses[index]
                const active = index === activeIndex
                return (
                  <button
                    key={question.id}
                    type="button"
                    className={`min-h-[44px] rounded-lg border px-2 py-2 text-sm font-semibold transition-colors ${statusClass(status, active)}`}
                    onClick={() => goTo(index)}
                    aria-current={active ? 'true' : undefined}
                  >
                    <span className="block">{index + 1}</span>
                    <span className="sr-only">
                      第 {index + 1} 題，{statusLabel(status)}{active ? '，目前題' : ''}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </section>

      {selectableChapters.length > 1 && (
        <section className="surface mb-4 p-4 sm:p-5">
          <div className="section-title mb-2">切換章節</div>
          <div className="flex flex-wrap gap-2">
            {selectableChapters.map((item, index) => {
              const count = activeSummary?.chapterCounts[item.id] ?? 0
              return (
                <Link
                  key={item.id}
                  to={chapterRoute(item.id)}
                  className={`btn-outline min-h-[44px] ${
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
        </section>
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

      <MobileActionBar className="sm:hidden">
        <button
          className="btn-outline min-h-[44px] flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex - 1)}
          disabled={activeIndex === 0}
        >
          ← 上一題
        </button>
        <div className="min-w-[84px] shrink-0 text-center text-[0.76rem] text-text-light">
          <div className="font-semibold text-primary">第 {activeIndex + 1} 題</div>
          <div>{statusLabel(currentStatus)} · {answeredCount}/{chapter.questions.length}</div>
        </div>
        <button
          className="btn-outline min-h-[44px] flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex + 1)}
          disabled={activeIndex === chapter.questions.length - 1}
        >
          下一題 →
        </button>
      </MobileActionBar>
      <div className="sr-only" aria-live="polite">{activeQuestionNavLabel}</div>
    </div>
  )
}
