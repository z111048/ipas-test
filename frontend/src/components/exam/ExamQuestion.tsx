import { useExamStore } from '../../store/examStore'
import type { Question } from '../../types'

interface ExamQuestionProps {
  question: Question
  index: number
}

export default function ExamQuestion({ question, index }: ExamQuestionProps) {
  const selected = useExamStore((s) => s.userAnswers[index])
  const selectAnswer = useExamStore((s) => s.selectAnswer)

  return (
    <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
      <div className="text-[0.78rem] text-text-light font-semibold mb-2 uppercase tracking-wide">
        第 {index + 1} 題
      </div>
      <div className="text-[0.95rem] leading-relaxed mb-4 text-app-text">{question.question}</div>
      <div className="flex flex-col gap-2">
        {(['A', 'B', 'C', 'D'] as const).map((key) => (
          <label
            key={key}
            className={`flex items-start gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all text-[0.9rem] ${
              selected === key
                ? 'bg-[#eef5ff] border-accent text-primary font-medium'
                : 'bg-card border-border hover:bg-[#f5f7fa] hover:border-accent/50'
            }`}
            onClick={() => selectAnswer(index, key)}
          >
            <input
              type="radio"
              name={`q${index}`}
              value={key}
              checked={selected === key}
              onChange={() => selectAnswer(index, key)}
              className="mt-0.5 accent-accent"
            />
            <span>({key}) {question.options[key]}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
