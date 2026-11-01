import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChoiceOption, Dialog } from '../ui'
import { loadExamData } from '../../data/examLoaders'
import { loadSubjectQuestions } from '../../data/questionLoaders'
import { loadReferenceAnswers, referenceForQuestion } from '../../data/referenceAnswerLoaders'
import type { ExamReferenceAnswer, Question } from '../../types'
import { cleanExamText } from '../../utils/examText'

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
          <div id={descriptionId} className="text-meta text-text-light">
            {item.level} · {item.source}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="btn-outline btn-sm shrink-0"
          >
            關閉 Esc
          </button>
        </div>

        {state === 'loading' && <p className="text-ui text-text-light">題目載入中…</p>}
        {state === 'missing' && (
          <p className="text-ui text-text-light">
            載不到這一題的內容，
            <Link to={item.route} className="text-accent">改到原頁面查看</Link>。
          </p>
        )}

        {state === 'ready' && question && (
          <>
            {/* data-exam-text：tests/test_layout_audit.py 以此找題目文字，驗沒有 PDF 斷行空白。
                公告試題已在 loadExamData 清過；這裡再清一次涵蓋章節練習題（冪等）。 */}
            <div data-exam-text className="mb-4 text-reading leading-8 text-app-text content-justify">
              {cleanExamText(question.question)}
            </div>

            <div className="flex flex-col gap-2">
              {OPTIONS.map((key) => {
                const isAnswer = key === answer
                const isPicked = key === picked
                const show = revealed || picked !== null
                const state = !show ? undefined : isAnswer ? 'correct' : isPicked ? 'wrong' : 'idle'
                return (
                  <ChoiceOption
                    key={key}
                    kind="button"
                    letter={key}
                    selected={isPicked}
                    onSelect={() => setPicked(key)}
                    locked={show}
                    state={state}
                  >
                    <span data-exam-text>{cleanExamText(question.options[key])}</span>
                  </ChoiceOption>
                )
              })}
            </div>

            {picked === null && !revealed && (
              <button
                type="button"
                onClick={() => setRevealed(true)}
                className="btn-outline mt-3"
              >
                直接看答案
              </button>
            )}

            {(revealed || picked !== null) && (
              <div className="mt-4 border-t border-border pt-3">
                <div className="mb-1 text-ui font-semibold text-primary">
                  正確答案（{answer}）
                </div>
                {question.explanation && (
                  <p className="m-0 text-reading leading-7 text-app-text content-justify">
                    {question.explanation}
                  </p>
                )}
                {reference && (
                  <div className="mt-3 rounded-lg bg-answered-soft px-3 py-3 text-reading leading-7 text-app-text content-justify">
                    {reference.reference_answer}
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 border-t border-border pt-3 text-ui">
              <Link to={item.route} className="text-link">
                在{item.kind === 'exam' ? '整份考卷' : '這一章的練習'}裡開啟 →
              </Link>
            </div>
          </>
        )}
      </div>
    </Dialog>
  )
}
