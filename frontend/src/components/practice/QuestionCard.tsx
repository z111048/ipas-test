import { useState } from 'react'
import type { Question } from '../../types'
import OptionButton from './OptionButton'
import CardPanel from './CardPanel'

interface QuestionCardProps {
  question: Question
  index: number
  selected: 'A' | 'B' | 'C' | 'D' | null
  onSelect: (key: 'A' | 'B' | 'C' | 'D') => void
  isActive?: boolean
  registerRef?: (el: HTMLElement | null) => void
}

type OptionState = 'idle' | 'correct' | 'wrong'

export default function QuestionCard({ question, index, selected, onSelect, isActive, registerRef }: QuestionCardProps) {
  const [manualReveal, setManualReveal] = useState(false)
  const [cardOpen, setCardOpen] = useState(false)
  const answered = selected !== null
  const revealed = answered || manualReveal

  const handleSelect = (key: 'A' | 'B' | 'C' | 'D') => {
    if (selected !== null) return
    onSelect(key)
  }

  const getState = (key: 'A' | 'B' | 'C' | 'D'): OptionState => {
    if (!revealed) return 'idle'
    if (key === question.answer) return 'correct'
    if (key === selected) return 'wrong'
    return 'idle'
  }

  const resultMessage = answered
    ? selected === question.answer
      ? `第 ${index + 1} 題答對了，正確答案為 (${question.answer})。`
      : `第 ${index + 1} 題答錯了，正確答案為 (${question.answer})，您選擇的是 (${selected})。`
    : ''

  return (
    <article
      ref={registerRef}
      data-q-index={index}
      className={`surface p-5 mb-4 transition-shadow duration-150 ${
        isActive ? 'ring-2 ring-accent/50' : ''
      }`}
    >
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

      <div aria-live="polite" className="sr-only">{resultMessage}</div>

      {!revealed && (
        <button
          className="btn-outline mt-3 cursor-pointer"
          onClick={() => setManualReveal(true)}
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
