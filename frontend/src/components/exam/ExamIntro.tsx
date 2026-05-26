import type { ExamData } from '../../types'

interface ExamIntroProps {
  examData: ExamData
  onStart: () => void
}

export default function ExamIntro({ examData, onStart }: ExamIntroProps) {
  return (
    <div className="page-shell">
      <div className="page-header text-center">
        <div className="eyebrow mb-2">Mock exam</div>
        <h1 className="text-2xl font-bold text-primary mb-4">{examData.exam}</h1>
        <div className="mb-6 flex flex-wrap justify-center gap-2 text-[0.86rem]">
          <span className="pill">共 {examData.total} 題</span>
          <span className="pill pill-muted">考試時間：{examData.time_limit}</span>
          <span className="pill pill-muted">及格分數：{examData.passing_score} 分</span>
        </div>
        <button className="btn-primary min-w-[9rem] cursor-pointer border-0" onClick={onStart}>
          開始考試
        </button>
      </div>
    </div>
  )
}
