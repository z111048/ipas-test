import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Dialog, MobileActionBar, StatePanel } from '../components/ui'
import { loadExamData } from '../data/examLoaders'
import { useExamTimer } from '../hooks/useExamTimer'
import { useExamStore } from '../store/examStore'
import type { ExamData } from '../types'
import { preferredScrollBehavior } from '../utils/motion'
import ExamIntro from '../components/exam/ExamIntro'
import ExamQuestion from '../components/exam/ExamQuestion'
import ExamResults from '../components/exam/ExamResults'
import ExamTimer from '../components/exam/ExamTimer'

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

function formatRemaining(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes} 分 ${String(remainingSeconds).padStart(2, '0')} 秒`
}

export default function ExamPage() {
  const { examKey } = useParams<{ examKey: string }>()
  const [examData, setExamData] = useState<ExamData | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [showPalette, setShowPalette] = useState(false)
  const [showSubmitDialog, setShowSubmitDialog] = useState(false)
  const questionRefs = useRef<Array<HTMLElement | null>>([])
  const confirmSubmitRef = useRef<HTMLButtonElement>(null)
  const [searchParams] = useSearchParams()
  const targetQuestionId = searchParams.get('q')

  const phase = useExamStore((s) => s.phase)
  const storeExamKey = useExamStore((s) => s.examKey)
  const setExam = useExamStore((s) => s.setExam)
  const startExam = useExamStore((s) => s.startExam)
  const submitExam = useExamStore((s) => s.submitExam)
  const resetExam = useExamStore((s) => s.resetExam)
  const selectAnswer = useExamStore((s) => s.selectAnswer)
  const userAnswers = useExamStore((s) => s.userAnswers)
  const currentExamData = useExamStore((s) => s.examData)
  const secondsRemaining = useExamStore((s) => s.secondsRemaining)

  useExamTimer(phase === 'active')

  const goTo = (idx: number) => {
    const total = currentExamData?.questions.length ?? 0
    if (total === 0) return
    const clamped = Math.max(0, Math.min(idx, total - 1))
    setActiveIndex(clamped)
    questionRefs.current[clamped]?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'center' })
  }

  useEffect(() => {
    if (phase !== 'active' || !currentExamData || showSubmitDialog) return
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return
      if (['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault()
        const optKey = (['A', 'B', 'C', 'D'] as const)[Number(event.key) - 1]
        selectAnswer(activeIndex, optKey)
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
  }, [phase, currentExamData, activeIndex, selectAnswer, showSubmitDialog])

  useEffect(() => {
    if (phase !== 'active' || !currentExamData) return
    questionRefs.current = []
    setActiveIndex(0)
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const closest = visible.reduce((a, b) => (a.intersectionRatio > b.intersectionRatio ? a : b))
        const idx = Number((closest.target as HTMLElement).dataset.qIndex)
        if (!Number.isNaN(idx)) setActiveIndex(idx)
      },
      { threshold: [0.3, 0.6, 0.9], rootMargin: '-120px 0px -35% 0px' },
    )
    const id = window.setTimeout(() => {
      questionRefs.current.forEach((el) => el && observer.observe(el))
    }, 0)
    return () => {
      window.clearTimeout(id)
      observer.disconnect()
    }
  }, [phase, currentExamData])

  useEffect(() => {
    let active = true
    setExamData(undefined)
    setLoadError(null)
    if (!examKey) return

    setLoading(true)
    loadExamData(examKey)
      .then((loadedData) => {
        if (active) setExamData(loadedData)
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
  }, [examKey])

  useEffect(() => {
    if (examData && examKey && (examKey !== storeExamKey || currentExamData !== examData)) {
      setExam(examData, examKey)
    }
  }, [examKey, examData, storeExamKey, currentExamData, setExam])

  useEffect(() => {
    if (targetQuestionId && phase === 'active') return
    window.scrollTo(0, 0)
  }, [examKey, phase, targetQuestionId])

  useEffect(() => {
    if (!targetQuestionId || phase !== 'active' || !currentExamData) return
    const index = currentExamData.questions.findIndex((q) => q.id === targetQuestionId)
    if (index < 0) return
    const timer = window.setTimeout(() => {
      setActiveIndex(index)
      questionRefs.current[index]?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'center' })
    }, 120)
    return () => window.clearTimeout(timer)
  }, [targetQuestionId, phase, currentExamData])

  useEffect(() => {
    if (phase !== 'active') {
      setShowPalette(false)
      setShowSubmitDialog(false)
    }
  }, [phase])

  if (loading) {
    return <div className="page-shell text-text-light p-4">考卷載入中...</div>
  }

  if (loadError) {
    return <div className="page-shell text-error p-4">考卷載入失敗：{loadError}</div>
  }

  if (!examData) {
    return <div className="page-shell text-error p-4">找不到考試：{examKey}</div>
  }

  if (examKey !== storeExamKey || currentExamData !== examData) {
    return <div className="page-shell text-text-light p-4">考卷準備中...</div>
  }

  const targetIndex = targetQuestionId
    ? examData.questions.findIndex((q) => q.id === targetQuestionId)
    : -1

  if (phase === 'intro') {
    return (
      <>
        {targetIndex >= 0 && (
          <div className="page-shell">
            <StatePanel className="mb-4">
              開始作答後會自動跳到<strong>第 {targetIndex + 1} 題</strong>
              （你從概念索引點進來的那一題）。
            </StatePanel>
          </div>
        )}
        <ExamIntro examData={examData} onStart={startExam} />
      </>
    )
  }

  if (phase === 'results') {
    return <ExamResults onRetry={resetExam} />
  }

  const answeredCount = Object.keys(userAnswers).length
  const unansweredIndices = currentExamData.questions
    .map((_, index) => index)
    .filter((index) => !userAnswers[index])
  const unansweredCount = unansweredIndices.length
  const activeAnswered = Boolean(userAnswers[activeIndex])
  const currentAnswer = userAnswers[activeIndex]

  const jumpToFirstUnanswered = () => {
    const nextIndex = unansweredIndices[0]
    if (typeof nextIndex !== 'number') return
    setShowPalette(false)
    setShowSubmitDialog(false)
    goTo(nextIndex)
  }

  const handleSubmitIntent = () => {
    setShowSubmitDialog(true)
  }

  const handleConfirmSubmit = () => {
    setShowSubmitDialog(false)
    submitExam()
  }

  return (
    <div className="page-shell pb-28 sm:pb-6">
      <div className="sticky top-0 z-20 mb-3">
        <div className="rounded-xl border border-[#b8cce2] bg-primary p-2 text-white shadow-lg sm:p-3">
          <div className="flex items-center justify-between gap-2">
            <ExamTimer compact />
            <div className="min-w-0 text-center">
              <div className="text-[0.8rem] font-semibold">已答 {answeredCount}/{currentExamData.total}</div>
              <div className="text-[0.68rem] text-white/72">
                {unansweredCount === 0 ? '全部已答' : `未答 ${unansweredCount} 題`}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                className="min-h-[44px] rounded-md border border-white/20 bg-white/8 px-2 py-2 text-[0.74rem] font-semibold text-white sm:px-3 sm:text-[0.78rem]"
                onClick={() => setShowPalette((open) => !open)}
                aria-expanded={showPalette}
              >
                題號盤
              </button>
              <button
                type="button"
                className="min-h-[44px] rounded-md border border-white/20 bg-white px-2 py-2 text-[0.78rem] font-semibold text-primary sm:px-3 sm:text-[0.82rem]"
                onClick={handleSubmitIntent}
              >
                繳卷
              </button>
            </div>
          </div>
          <div className="mt-1 flex min-w-0 items-center gap-2 text-[0.72rem] text-white/70">
            <span className="shrink-0 font-semibold uppercase tracking-[0.12em]">模擬考試</span>
            <span className="truncate text-white/85">{currentExamData.exam}</span>
          </div>
        </div>
      </div>

      {showPalette && (
        <section className="surface mb-4 p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="section-title">題號盤</div>
              <p className="mt-1 text-[0.84rem] leading-6 text-text-light">
                目前在第 {activeIndex + 1} 題。
                {unansweredCount === 0 ? ' 全部題目都已作答。' : ` 還有 ${unansweredCount} 題未答。`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {unansweredCount > 0 && (
                <button
                  type="button"
                  className="btn-outline min-h-[44px]"
                  onClick={jumpToFirstUnanswered}
                >
                  跳到第一題未答
                </button>
              )}
              <button
                type="button"
                className="btn-outline min-h-[44px]"
                onClick={() => setShowPalette(false)}
              >
                收起題號盤
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-7 lg:grid-cols-10">
            {currentExamData.questions.map((question, index) => {
              const isActive = index === activeIndex
              const isAnswered = Boolean(userAnswers[index])
              return (
                <button
                  key={question.id}
                  type="button"
                  className={`min-h-[44px] rounded-lg border px-2 py-2 text-sm font-semibold transition-colors ${
                    isActive
                      ? 'border-accent bg-[#eff6ff] text-primary ring-2 ring-accent/35 ring-offset-2'
                      : isAnswered
                        ? 'border-success/30 bg-[#ecfdf3] text-success'
                        : 'border-border bg-white text-text-light'
                  }`}
                  onClick={() => goTo(index)}
                  aria-current={isActive ? 'true' : undefined}
                >
                  <span className="block">{index + 1}</span>
                  <span className="sr-only">
                    第 {index + 1} 題，{isAnswered ? '已作答' : '未作答'}{isActive ? '，目前題' : ''}
                  </span>
                </button>
              )
            })}
          </div>
        </section>
      )}

      <StatePanel className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>鍵盤：1–4 選答，←→ 切換上下題。</span>
          {unansweredCount > 0 && (
            <button
              type="button"
              className="btn-outline min-h-[44px]"
              onClick={jumpToFirstUnanswered}
            >
              跳到未答題
            </button>
          )}
        </div>
      </StatePanel>

      {currentExamData.questions.map((q, i) => (
        <ExamQuestion
          key={q.id}
          question={q}
          index={i}
          isActive={i === activeIndex}
          registerRef={(el) => {
            questionRefs.current[i] = el
          }}
        />
      ))}

      <div className="hidden py-4 text-center sm:block">
        <button
          type="button"
          className="btn-primary min-h-[44px] cursor-pointer border-0 px-8 py-3 text-base"
          onClick={handleSubmitIntent}
        >
          繳卷交答案
        </button>
      </div>

      <MobileActionBar className="sm:hidden">
        <button
          className="btn-outline min-h-[44px] flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex - 1)}
          disabled={activeIndex === 0}
        >
          ← 上一題
        </button>
        <div className="min-w-[92px] shrink-0 text-center text-[0.76rem] text-text-light">
          <div className="font-semibold text-primary">第 {activeIndex + 1} 題</div>
          <div>
            {currentAnswer ? `已選 ${currentAnswer}` : '未作答'} · {answeredCount}/{currentExamData.questions.length}
          </div>
        </div>
        <button
          className="btn-outline min-h-[44px] flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex + 1)}
          disabled={activeIndex === currentExamData.questions.length - 1}
        >
          下一題 →
        </button>
      </MobileActionBar>

      <Dialog
        open={showSubmitDialog}
        title="確認繳卷"
        onClose={() => setShowSubmitDialog(false)}
        initialFocusRef={confirmSubmitRef}
      >
        <div className="p-5 sm:p-6">
          <div className="mb-1 text-sm font-semibold text-primary">確認繳卷</div>
          <h2 className="text-xl font-bold text-app-text">要現在結束作答嗎？</h2>
          <div className="mt-4 space-y-3 text-[0.92rem] leading-7 text-app-text">
            <p>剩餘時間：{formatRemaining(secondsRemaining)}</p>
            <p>{unansweredCount === 0 ? '所有題目都已作答。' : `還有 ${unansweredCount} 題未作答。`}</p>
            {activeAnswered ? (
              <p>目前停留在第 {activeIndex + 1} 題，已完成作答。</p>
            ) : (
              <p>目前停留在第 {activeIndex + 1} 題，尚未作答。</p>
            )}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {unansweredCount > 0 && (
              <button
                type="button"
                className="btn-outline min-h-[44px]"
                onClick={jumpToFirstUnanswered}
              >
                先看未答題
              </button>
            )}
            <button
              type="button"
              className="btn-outline min-h-[44px]"
              onClick={() => setShowSubmitDialog(false)}
            >
              返回作答
            </button>
            <button
              ref={confirmSubmitRef}
              type="button"
              className="btn-primary min-h-[44px] border-0"
              onClick={handleConfirmSubmit}
            >
              確認繳卷
            </button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
