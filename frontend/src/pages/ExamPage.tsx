import { useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useExamStore } from '../store/examStore'
import { useExamTimer } from '../hooks/useExamTimer'
import { loadExamData } from '../data/examLoaders'
import type { ExamData } from '../types'
import ExamIntro from '../components/exam/ExamIntro'
import ExamTimer from '../components/exam/ExamTimer'
import ExamQuestion from '../components/exam/ExamQuestion'
import ExamResults from '../components/exam/ExamResults'

export default function ExamPage() {
  const { examKey } = useParams<{ examKey: string }>()
  const [examData, setExamData] = useState<ExamData | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const phase = useExamStore((s) => s.phase)
  const storeExamKey = useExamStore((s) => s.examKey)
  const setExam = useExamStore((s) => s.setExam)
  const startExam = useExamStore((s) => s.startExam)
  const submitExam = useExamStore((s) => s.submitExam)
  const resetExam = useExamStore((s) => s.resetExam)
  const userAnswers = useExamStore((s) => s.userAnswers)
  const currentExamData = useExamStore((s) => s.examData)

  useExamTimer(phase === 'active')

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
    window.scrollTo(0, 0)
  }, [examKey, phase])

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

  if (phase === 'intro') {
    return <ExamIntro examData={examData} onStart={startExam} />
  }

  if (phase === 'results') {
    return <ExamResults onRetry={resetExam} />
  }

  const answeredCount = Object.keys(userAnswers).length

  return (
    <div className="page-shell">
      <div className="sticky top-0 z-20 mb-4 rounded-lg border border-[#b8cce2] bg-primary text-white shadow-lg">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="text-[0.74rem] font-semibold uppercase tracking-wide text-white/60">模擬考試</div>
            <div className="truncate text-[0.9rem] font-semibold">{currentExamData.exam}</div>
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
        <ExamQuestion key={q.id} question={q} index={i} />
      ))}

      <div className="text-center py-4">
        <button
          className="btn-primary cursor-pointer border-0 px-8 py-3 text-base"
          onClick={submitExam}
        >
          繳卷交答案
        </button>
      </div>
    </div>
  )
}
