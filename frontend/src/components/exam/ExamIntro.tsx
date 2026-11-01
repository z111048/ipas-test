import type { SavedExamAttempt } from '../../store/examStore'
import type { ExamData } from '../../types'

interface ExamIntroProps {
  examData: ExamData
  onStart: () => void
  savedAttempt?: SavedExamAttempt | null
  onResume?: () => void
}

function formatClock(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export default function ExamIntro({ examData, onStart, savedAttempt, onResume }: ExamIntroProps) {
  const canResume = Boolean(savedAttempt && onResume)
  const answeredCount = savedAttempt ? Object.keys(savedAttempt.answers).length : 0

  return (
    <div className="page-shell">
      <div className="page-header text-center">
        <div className="eyebrow mb-2">公告試題</div>
        <h1 className="text-2xl font-bold text-primary mb-4">{examData.exam}</h1>
        <div className="mb-6 flex flex-wrap justify-center gap-2 text-[0.86rem]">
          <span className="pill">共 {examData.total} 題</span>
          <span className="pill pill-muted">考試時間：{examData.time_limit}</span>
          <span className="pill pill-muted">及格分數：{examData.passing_score} 分</span>
        </div>
        {canResume && savedAttempt ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-[0.88rem] leading-6 text-text-light">
              你有一份尚未繳卷的作答，剩餘時間 {formatClock(savedAttempt.secondsRemaining)}。
              離開期間不計時。
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <button
                type="button"
                className="btn-primary min-h-[44px] min-w-[9rem] cursor-pointer border-0"
                onClick={onResume}
              >
                繼續上次作答（已答 {answeredCount} 題）
              </button>
              <button
                type="button"
                className="btn-outline min-h-[44px] min-w-[9rem] cursor-pointer"
                onClick={onStart}
              >
                重新開始
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="btn-primary min-h-[44px] min-w-[9rem] cursor-pointer border-0"
            onClick={onStart}
          >
            開始考試
          </button>
        )}
      </div>
    </div>
  )
}
