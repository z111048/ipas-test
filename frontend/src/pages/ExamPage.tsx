import { useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useExamStore } from '../store/examStore'
import { useExamTimer } from '../hooks/useExamTimer'
import { loadExamData } from '../data/examLoaders'
import type { ExamData } from '../types'
import ExamIntro from '../components/exam/ExamIntro'
import ExamTimer from '../components/exam/ExamTimer'
import ExamQuestion from '../components/exam/ExamQuestion'
import ExamResults from '../components/exam/ExamResults'

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

export default function ExamPage() {
  const { examKey } = useParams<{ examKey: string }>()
  const [examData, setExamData] = useState<ExamData | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const questionRefs = useRef<Array<HTMLElement | null>>([])
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

  useExamTimer(phase === 'active')

  const goTo = (idx: number) => {
    const total = currentExamData?.questions.length ?? 0
    if (total === 0) return
    const clamped = Math.max(0, Math.min(idx, total - 1))
    setActiveIndex(clamped)
    questionRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // 鍵盤操作：1-4 選答，←/→ 切換上下題（僅在測驗進行中生效）
  useEffect(() => {
    if (phase !== 'active' || !currentExamData) return
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
  }, [phase, currentExamData, activeIndex, selectAnswer])

  // 捲動時追蹤目前題號
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
      { threshold: [0.3, 0.6, 0.9], rootMargin: '-140px 0px -35% 0px' },
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
      setExam(examData, examKey!)
    }
  }, [examKey, examData, storeExamKey, currentExamData, setExam])

  useEffect(() => {
    // 帶 ?q= 且已經開始作答時不回頂端，讓下面的定位接手
    if (targetQuestionId && phase === 'active') return
    window.scrollTo(0, 0)
  }, [examKey, phase, targetQuestionId])

  // ?q=<題號>：捲到那一題。考卷是計時測驗，不會自動開始——所以定位是在使用者
  // 按下「開始作答」、phase 變成 active 之後才發生。
  useEffect(() => {
    if (!targetQuestionId || phase !== 'active' || !currentExamData) return
    const index = currentExamData.questions.findIndex((q) => q.id === targetQuestionId)
    if (index < 0) return
    const timer = window.setTimeout(() => {
      setActiveIndex(index)
      questionRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 120)
    return () => window.clearTimeout(timer)
  }, [targetQuestionId, phase, currentExamData])

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

  // 從概念索引帶 ?q= 進來會先落在說明頁（計時測驗不會自動開始），
  // 不說明的話那個連結看起來就像壞掉了
  const targetIndex = targetQuestionId
    ? examData.questions.findIndex((q) => q.id === targetQuestionId)
    : -1

  if (phase === 'intro') {
    return (
      <>
        {targetIndex >= 0 && (
          <div className="page-shell">
            <div className="surface mb-4 border-l-4 border-accent p-4 text-[0.88rem] text-app-text">
              開始作答後會自動跳到<strong>第 {targetIndex + 1} 題</strong>
              （你從概念索引點進來的那一題）。
            </div>
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

  return (
    <div className="page-shell pb-24 sm:pb-4">
      <div className="sticky top-0 z-20 mb-4 rounded-lg border border-[#b8cce2] bg-primary text-white shadow-lg">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="text-[0.74rem] font-semibold uppercase tracking-wide text-white/60">模擬考試</div>
            <div className="truncate text-[0.9rem] font-semibold">{currentExamData.exam}</div>
            <div className="mt-0.5 text-[0.7rem] text-white/60">鍵盤：1–4 選答，←→ 切換上下題</div>
          </div>
          <ExamTimer />
          <div className="flex items-center justify-between gap-3 md:justify-end">
            <div className="text-[0.8rem] text-white/80">已答：{answeredCount} / {currentExamData.total}</div>
            <button
              className="rounded-md border border-white/20 bg-white px-4 py-2 text-[0.82rem] font-semibold text-primary transition-colors hover:bg-slate-100 cursor-pointer"
              onClick={submitExam}
            >
              繳卷
            </button>
          </div>
        </div>
      </div>

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

      <div className="text-center py-4">
        <button
          className="btn-primary cursor-pointer border-0 px-8 py-3 text-base"
          onClick={submitExam}
        >
          繳卷交答案
        </button>
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
          {activeIndex + 1} / {currentExamData.questions.length}
        </span>
        <button
          className="btn-outline flex-1 disabled:opacity-40"
          onClick={() => goTo(activeIndex + 1)}
          disabled={activeIndex === currentExamData.questions.length - 1}
        >
          下一題 →
        </button>
      </div>
    </div>
  )
}
