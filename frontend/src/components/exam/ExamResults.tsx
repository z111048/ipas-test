import { useExamStore } from '../../store/examStore'
import ProgressBar from '../shared/ProgressBar'
import StatBox from '../shared/StatBox'

interface ExamResultsProps {
  onRetry: () => void
}

export default function ExamResults({ onRetry }: ExamResultsProps) {
  const examData = useExamStore((s) => s.examData)!
  const userAnswers = useExamStore((s) => s.userAnswers)

  let correct = 0, wrong = 0, skipped = 0
  examData.questions.forEach((q, i) => {
    if (userAnswers[i] === q.answer) correct++
    else if (userAnswers[i]) wrong++
    else skipped++
  })

  const total = examData.questions.length
  const score = Math.round((correct / total) * 100)
  const pass = score >= examData.passing_score

  return (
    <div>
      <div className="bg-card rounded-xl shadow-sm border border-border p-8 text-center mb-6">
        <div className="text-text-light mb-2">{examData.exam}</div>
        <div className={`text-6xl font-bold mb-2 ${pass ? 'text-success' : 'text-error'}`}>
          {score} 分
        </div>
        <div className="text-lg mb-6">{pass ? '🎉 恭喜通過！' : '❌ 尚未通過，繼續加油！'}</div>
        <div className="flex gap-3 flex-wrap justify-center mb-6">
          <StatBox value={correct} label="答對" valueColor="text-success" />
          <StatBox value={wrong} label="答錯" valueColor="text-error" />
          <StatBox value={skipped} label="未答" valueColor="text-text-light" />
          <StatBox value={total} label="總題數" />
        </div>
        <ProgressBar
          percent={score}
          color={pass ? 'bg-success' : 'bg-error'}
          height="h-3"
        />
        <div className="text-[0.8rem] text-text-light mt-2">及格線：{examData.passing_score} 分</div>
        <button
          className="mt-6 border border-accent text-accent rounded-lg px-6 py-2 text-[0.88rem] hover:bg-accent hover:text-white transition-colors cursor-pointer bg-transparent"
          onClick={onRetry}
        >
          重新考試
        </button>
      </div>

      <h2 className="text-lg font-semibold text-primary mb-4">📝 詳細解析</h2>
      {examData.questions.map((q, i) => {
        const ua = userAnswers[i]
        const isCorrect = ua === q.answer
        const isSkipped = !ua
        return (
          <div
            key={q.id}
            className={`bg-card rounded-xl border p-5 mb-3 ${
              isCorrect ? 'border-success/30' : isSkipped ? 'border-border' : 'border-error/30'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[0.78rem] text-text-light font-semibold uppercase tracking-wide">
                第 {i + 1} 題
              </span>
              <span
                className={`text-[0.75rem] px-2 py-0.5 rounded-full font-medium ${
                  isCorrect
                    ? 'bg-[#eafaf1] text-success'
                    : isSkipped
                      ? 'bg-[#fef5e7] text-warning'
                      : 'bg-[#fdf2f2] text-error'
                }`}
              >
                {isCorrect ? '✓ 正確' : isSkipped ? '— 未作答' : '✗ 錯誤'}
              </span>
            </div>
            <div className="text-[0.92rem] mb-3 text-app-text">{q.question}</div>
            <div className="text-[0.85rem] space-y-1">
              {!isCorrect && !isSkipped && (
                <div className="text-error">
                  您的答案：({ua}) {q.options[ua!]}
                </div>
              )}
              <div className="text-success">
                正確答案：({q.answer}) {q.options[q.answer]}
              </div>
            </div>
            {q.explanation && (
              <div className="mt-3 bg-[#f8f9fa] rounded-lg p-3 text-[0.85rem] text-text-light leading-relaxed">
                {q.explanation}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
