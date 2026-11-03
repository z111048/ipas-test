import { useId, useRef, useState } from 'react'
import type { Question } from '../../types'
import { ChoiceOption, type ChoiceState } from '../ui'
import CardPanel from './CardPanel'
import { celebrateCorrectAnswer } from '../../features/seasonal'

interface QuestionCardProps {
  question: Question
  index: number
  selected: 'A' | 'B' | 'C' | 'D' | null
  onSelect: (key: 'A' | 'B' | 'C' | 'D') => void
  isActive?: boolean
  registerRef?: (el: HTMLElement | null) => void
}

/** 該題某個選項的按鈕（ChoiceOption kind="button" 依 A–D 順序渲染 aria-pressed 按鈕）。 */
export function choiceButton(article: HTMLElement | null | undefined, key: 'A' | 'B' | 'C' | 'D') {
  return article?.querySelectorAll<HTMLElement>('button[aria-pressed]')[['A', 'B', 'C', 'D'].indexOf(key)] ?? article
}

export default function QuestionCard({ question, index, selected, onSelect, isActive, registerRef }: QuestionCardProps) {
  const [manualReveal, setManualReveal] = useState(false)
  const [cardOpen, setCardOpen] = useState(false)
  const resultId = useId()
  const answered = selected !== null
  const revealed = answered || manualReveal

  const articleRef = useRef<HTMLElement | null>(null)

  const handleSelect = (key: 'A' | 'B' | 'C' | 'D') => {
    if (selected !== null) return
    onSelect(key)
    if (key === question.answer) celebrateCorrectAnswer(choiceButton(articleRef.current, key))
  }

  /** 批改後才給 correct/wrong；未批改交給 ChoiceOption 依 selected 決定。 */
  const getState = (key: 'A' | 'B' | 'C' | 'D'): ChoiceState | undefined => {
    if (!revealed) return undefined
    if (key === question.answer) return 'correct'
    if (key === selected) return 'wrong'
    return 'idle'
  }

  const resultMessage = answered
    ? selected === question.answer
      ? `第 ${index + 1} 題答對了，正確答案為 (${question.answer})。`
      : `第 ${index + 1} 題答錯了，正確答案為 (${question.answer})，您選擇的是 (${selected})。`
    : manualReveal
      ? `第 ${index + 1} 題已顯示答案與解析，正確答案為 (${question.answer})。`
      : ''

  return (
    <article
      ref={(el) => {
        articleRef.current = el
        registerRef?.(el)
      }}
      data-q-index={index}
      className={`surface mb-4 p-4 transition-shadow duration-150 sm:p-5 ${
        isActive ? 'ring-2 ring-accent/50' : ''
      }`}
    >
      <h2 className="eyebrow mb-2">第 {index + 1} 題</h2>
      <div className="text-reading mb-4 text-app-text content-justify">{question.question}</div>

      <div className="flex flex-col gap-2">
        {(['A', 'B', 'C', 'D'] as const).map((key) => (
          <ChoiceOption
            key={key}
            kind="button"
            letter={key}
            selected={selected === key}
            locked={selected !== null}
            state={getState(key)}
            describedBy={resultMessage ? resultId : undefined}
            onSelect={() => handleSelect(key)}
          >
            {question.options[key]}
          </ChoiceOption>
        ))}
      </div>

      <div id={resultId} aria-live="polite" className="sr-only">{resultMessage}</div>

      {!revealed && (
        <button type="button" className="btn-outline mt-3" onClick={() => setManualReveal(true)}>
          顯示答案與解析
        </button>
      )}

      {revealed && (
        <div className="mt-4 rounded-lg bg-panel p-4 text-reading text-app-text content-justify">
          <strong className="block">正確答案：({question.answer}) {question.options[question.answer]}</strong>
          {question.explanation && <p className="mt-3">{question.explanation}</p>}
        </div>
      )}

      {revealed && question.card && (
        <>
          <button
            type="button"
            className="btn-outline mt-3"
            onClick={() => setCardOpen((o) => !o)}
            aria-expanded={cardOpen}
          >
            {cardOpen ? '收起解說圖卡' : '查看解說圖卡'}
          </button>
          {cardOpen && <CardPanel card={question.card} questionId={question.id} />}
        </>
      )}
    </article>
  )
}
