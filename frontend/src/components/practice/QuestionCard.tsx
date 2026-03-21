import { useState } from 'react'
import type { Question } from '../../types'
import OptionButton from './OptionButton'
import CardPanel from './CardPanel'

interface QuestionCardProps {
  question: Question
  index: number
}

type OptionState = 'idle' | 'correct' | 'wrong'

export default function QuestionCard({ question, index }: QuestionCardProps) {
  const [selected, setSelected] = useState<'A' | 'B' | 'C' | 'D' | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [cardOpen, setCardOpen] = useState(false)

  const handleSelect = (key: 'A' | 'B' | 'C' | 'D') => {
    if (selected !== null) return
    setSelected(key)
    setRevealed(true)
  }

  const getState = (key: 'A' | 'B' | 'C' | 'D'): OptionState => {
    if (!revealed) return 'idle'
    if (key === question.answer) return 'correct'
    if (key === selected) return 'wrong'
    return 'idle'
  }

  return (
    <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
      <div className="text-[0.78rem] text-text-light font-semibold mb-2 uppercase tracking-wide">
        第 {index + 1} 題
      </div>
      <div className="text-[0.95rem] leading-relaxed mb-4 text-app-text">{question.question}</div>

      <div className="flex flex-col gap-2">
        {(['A', 'B', 'C', 'D'] as const).map((key) => (
          <OptionButton
            key={key}
            optKey={key}
            value={question.options[key]}
            state={getState(key)}
            disabled={selected !== null}
            onClick={() => handleSelect(key)}
          />
        ))}
      </div>

      {!revealed && (
        <button
          className="mt-3 text-[0.85rem] text-accent border border-accent rounded-lg px-4 py-2 hover:bg-accent hover:text-white transition-colors cursor-pointer bg-transparent"
          onClick={() => setRevealed(true)}
        >
          顯示答案與解析
        </button>
      )}

      {revealed && (
        <div className="mt-4 bg-[#f0f9ff] border-l-4 border-accent rounded-lg p-4 text-[0.88rem] leading-relaxed">
          <strong>✅ 正確答案：({question.answer}) {question.options[question.answer]}</strong>
          <br /><br />
          {question.explanation}
        </div>
      )}

      {revealed && question.card && (
        <>
          <button
            className="mt-3 text-[0.82rem] text-primary-light border border-primary-light rounded-lg px-4 py-2 hover:bg-primary hover:text-white transition-colors cursor-pointer bg-transparent"
            onClick={() => setCardOpen((o) => !o)}
          >
            {cardOpen ? '📌 收起解說圖卡' : '📌 查看解說圖卡'}
          </button>
          {cardOpen && <CardPanel card={question.card} />}
        </>
      )}
    </div>
  )
}
