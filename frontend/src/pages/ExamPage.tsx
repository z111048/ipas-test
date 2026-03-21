import { useParams } from 'react-router-dom'
import { useEffect } from 'react'
import mock1 from '@data/questions/mock_exam1.json'
import mock2 from '@data/questions/mock_exam2.json'
import sample from '@data/questions/sample_exam.json'
import type { ExamData } from '../types'
import { useExamStore } from '../store/examStore'
import { useExamTimer } from '../hooks/useExamTimer'
import ExamIntro from '../components/exam/ExamIntro'
import ExamTimer from '../components/exam/ExamTimer'
import ExamQuestion from '../components/exam/ExamQuestion'
import ExamResults from '../components/exam/ExamResults'

const EXAM_DATA: Record<string, ExamData> = {
  mock1: mock1 as ExamData,
  mock2: mock2 as ExamData,
  sample: sample as ExamData,
}

export default function ExamPage() {
  const { examKey } = useParams<{ examKey: string }>()
  const examData = EXAM_DATA[examKey ?? '']

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
    if (examData && examKey !== storeExamKey) {
      setExam(examData, examKey!)
    }
  }, [examKey, examData, storeExamKey, setExam])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [phase])

  if (!examData) {
    return <div className="text-error p-4">找不到考試：{examKey}</div>
  }

  if (phase === 'intro' || !currentExamData) {
    return <ExamIntro examData={examData} onStart={startExam} />
  }

  if (phase === 'results') {
    return <ExamResults onRetry={resetExam} />
  }

  const answeredCount = Object.keys(userAnswers).length

  return (
    <div>
      <div className="sticky top-0 z-10 bg-primary text-white rounded-xl mb-4 p-4 flex items-center justify-between gap-4 shadow-md">
        <div>
          <div className="text-[0.78rem] opacity-70">模擬考試</div>
          <div className="text-[0.88rem] font-semibold">{currentExamData.exam}</div>
        </div>
        <ExamTimer />
        <div className="text-right">
          <div className="text-[0.78rem] opacity-80 mb-1">
            已答：{answeredCount} / {currentExamData.total}
          </div>
          <button
            className="bg-white text-primary text-[0.82rem] font-semibold px-4 py-1.5 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer border-0"
            onClick={submitExam}
          >
            繳卷
          </button>
        </div>
      </div>

      {currentExamData.questions.map((q, i) => (
        <ExamQuestion key={q.id} question={q} index={i} />
      ))}

      <div className="text-center py-4">
        <button
          className="bg-accent hover:bg-accent-hover text-white text-lg font-semibold px-8 py-3 rounded-xl transition-colors cursor-pointer border-0"
          onClick={submitExam}
        >
          繳卷交答案
        </button>
      </div>
    </div>
  )
}
