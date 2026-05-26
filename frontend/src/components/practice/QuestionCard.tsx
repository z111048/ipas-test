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
    <article className="surface p-5 mb-4">
      <div className="eyebrow mb-2">
        第 {index + 1} 題
      </div>
      <div className="text-[0.96rem] leading-8 mb-4 text-app-text content-justify">{question.question}</div>

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
          className="btn-outline mt-3 cursor-pointer"
          onClick={() => setRevealed(true)}
        >
          顯示答案與解析
        </button>
      )}

      {revealed && (
        <div className="mt-4 rounded-lg border border-[#bfdbfe] bg-[#eff6ff] p-4 text-[0.88rem] leading-7 content-justify">
          <strong>正確答案：({question.answer}) {question.options[question.answer]}</strong>
          <br /><br />
          {question.explanation}
        </div>
      )}

      {revealed && question.card && (
        <>
          <button
            className="btn-outline mt-3 cursor-pointer"
            onClick={() => setCardOpen((o) => !o)}
          >
            {cardOpen ? '收起解說圖卡' : '查看解說圖卡'}
          </button>
          {cardOpen && <CardPanel card={question.card} />}
        </>
      )}
    </article>
  )
}
