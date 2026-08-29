import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Dialog } from '../ui'
import { loadExamData } from '../../data/examLoaders'
import { loadSubjectQuestions } from '../../data/questionLoaders'
import { loadReferenceAnswers, referenceForQuestion } from '../../data/referenceAnswerLoaders'
import type { ExamReferenceAnswer, Question } from '../../types'

export interface QuestionRef {
  id: string
  level: string
  source: string
  route: string
  stem: string
  kind?: 'exam' | 'practice'
  examKey?: string
  subjectId?: string
  chapterId?: string
  practiceSet?: string
}

const OPTIONS = ['A', 'B', 'C', 'D'] as const

/** 題目內容不放在 conceptGraph.json 裡（1,561 題的選項與解析會讓它多好幾 MB），
 *  開彈窗才去載那一份題庫——`loadExamData` 與 `loadReferenceAnswers` 都有
 *  模組層快取，同一份只會抓一次。 */
async function fetchQuestion(item: QuestionRef): Promise<{
  question?: Question
  reference?: ExamReferenceAnswer
}> {
  if (item.kind === 'exam' && item.examKey) {
    const [exam, references] = await Promise.all([
      loadExamData(item.examKey),
      loadReferenceAnswers(item.examKey),
    ])
    const question = exam?.questions.find((q) => q.id === item.id)
    const reference = references
      ? referenceForQuestion(references, item.examKey, item.id)
      : undefined
    return { question, reference }
  }
  if (item.kind === 'practice' && item.subjectId) {
    const data = await loadSubjectQuestions(item.subjectId, item.practiceSet || undefined)
    const chapter = data?.chapters.find((c) => c.id === item.chapterId)
    return { question: chapter?.questions.find((q) => q.id === item.id) }
  }
  return {}
}

export default function QuestionModal({ item, onClose }: { item: QuestionRef; onClose: () => void }) {
  const [state, setState] = useState<'loading' | 'ready' | 'missing'>('loading')
  const [question, setQuestion] = useState<Question | undefined>()
  const [reference, setReference] = useState<ExamReferenceAnswer | undefined>()
  const [revealed, setRevealed] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const descriptionId = useId()

  useEffect(() => {
    let active = true
    setState('loading')
    setRevealed(false)
    setPicked(null)
    fetchQuestion(item)
      .then((result) => {
        if (!active) return
        setQuestion(result.question)
        setReference(result.reference)
        setState(result.question ? 'ready' : 'missing')
      })
      // 沒有這條的話網路失敗會卡在 state='loading'，「題目載入中…」永不結束
      .catch(() => {
        if (!active) return
        setState('missing')
      })
    return () => {
      active = false
    }
  }, [item])

  const answer = question?.answer

  return (
    <Dialog
      open
      title="題目內容"
      descriptionId={descriptionId}
      onClose={onClose}
      initialFocusRef={closeButtonRef}
      className="max-h-[88dvh] max-w-3xl p-5 sm:rounded-2xl"
    >
      <div>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div id={descriptionId} className="text-[0.78rem] text-text-light">
            {item.level} · {item.source}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="min-h-[44px] rounded-md border border-border px-3 py-2 text-[0.78rem] text-text-light hover:border-accent hover:text-accent cursor-pointer"
          >
            關閉 Esc
          </button>
        </div>

        {state === 'loading' && <p className="text-sm text-text-light">題目載入中…</p>}
        {state === 'missing' && (
          <p className="text-sm text-text-light">
            載不到這一題的內容，
            <Link to={item.route} className="text-accent">改到原頁面查看</Link>。
          </p>
        )}

        {state === 'ready' && question && (
          <>
            <div className="mb-4 text-[0.96rem] leading-8 text-app-text content-justify">
              {question.question}
            </div>

            <div className="flex flex-col gap-2">
              {OPTIONS.map((key) => {
                const isAnswer = key === answer
                const isPicked = key === picked
                const show = revealed || picked !== null
                const tone = !show
                  ? 'border-border bg-white hover:border-accent'
                  : isAnswer
                    ? 'border-success bg-success/10'
                    : isPicked
                      ? 'border-error bg-error/10'
                      : 'border-border bg-white opacity-70'
                return (
                  <button
                    key={key}
                    type="button"
                    disabled={show}
                    onClick={() => setPicked(key)}
                    className={`min-h-[44px] rounded-lg border px-3 py-2 text-left text-[0.9rem] leading-7 ${tone} ${
                      show ? '' : 'cursor-pointer'
                    }`}
                  >
                    <span className="mr-2 font-semibold text-primary">({key})</span>
                    {question.options[key]}
                  </button>
                )
              })}
            </div>

            {picked === null && !revealed && (
              <button
                type="button"
                onClick={() => setRevealed(true)}
                className="mt-3 min-h-[44px] rounded-lg border border-border px-3 py-2 text-[0.82rem] text-text-light hover:border-accent hover:text-accent cursor-pointer"
              >
                直接看答案
              </button>
            )}

            {(revealed || picked !== null) && (
              <div className="mt-4 border-t border-border pt-3">
                <div className="mb-1 text-[0.82rem] font-semibold text-primary">
                  正確答案（{answer}）
                </div>
                {question.explanation && (
                  <p className="m-0 text-[0.88rem] leading-7 text-app-text content-justify">
                    {question.explanation}
                  </p>
                )}
                {reference && (
                  <div className="mt-3 rounded-lg bg-[#f4f9fd] px-3 py-3 text-[0.86rem] leading-7 text-app-text content-justify">
                    {reference.reference_answer}
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 border-t border-border pt-3 text-[0.82rem]">
              <Link to={item.route} className="text-accent no-underline hover:underline">
                在{item.kind === 'exam' ? '整份考卷' : '這一章的練習'}裡開啟 →
              </Link>
            </div>
          </>
        )}
      </div>
    </Dialog>
  )
}
