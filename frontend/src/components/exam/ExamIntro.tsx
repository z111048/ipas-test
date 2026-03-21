import type { ExamData } from '../../types'

interface ExamIntroProps {
  examData: ExamData
  onStart: () => void
}

export default function ExamIntro({ examData, onStart }: ExamIntroProps) {
  return (
    <div className="flex flex-col items-center text-center py-12">
      <h2 className="text-2xl font-bold text-primary mb-3">{examData.exam}</h2>
      <p className="text-text-light mb-6">
        共 <strong>{examData.total}</strong> 題 &nbsp;|&nbsp; 考試時間：
        <strong>{examData.time_limit}</strong> &nbsp;|&nbsp; 及格分數：
        <strong>{examData.passing_score} 分</strong>
      </p>
      <button
        className="bg-accent hover:bg-accent-hover text-white text-lg font-semibold px-8 py-3 rounded-xl transition-colors cursor-pointer border-0"
        onClick={onStart}
      >
        開始考試 ▶
      </button>
    </div>
  )
}
