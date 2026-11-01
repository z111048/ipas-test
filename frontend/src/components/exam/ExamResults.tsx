import { useEffect, useRef, useState } from 'react'
import { useExamStore } from '../../store/examStore'
import type { ExamReferenceAnswer, QuestionImage } from '../../types'
import { loadReferenceAnswers, referenceForQuestion } from '../../data/referenceAnswerLoaders'
import ProgressBar from '../shared/ProgressBar'
import StatBox from '../shared/StatBox'
import { publicAsset } from '../../utils/assets'
import { preferredScrollBehavior } from '../../utils/motion'
import { scrollMainToTop } from '../../utils/scrollMain'
import { Badge, Chip, PageHeader } from '../ui'
import CodeSnippet from './CodeSnippet'

interface ExamResultsProps {
  onRetry: () => void
}

function imageAspectRatio(image: QuestionImage) {
  const [x0, y0, x1, y1] = image.bbox ?? []
  if (typeof x0 !== 'number' || typeof y0 !== 'number' || typeof x1 !== 'number' || typeof y1 !== 'number') {
    return undefined
  }
  const width = Math.max(x1 - x0, 1)
  const height = Math.max(y1 - y0, 1)
  return `${width} / ${height}`
}

function ScoreRing({ score, pass }: { score: number; pass: boolean }) {
  const radius = 54
  const stroke = 12
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - Math.min(Math.max(score, 0), 100) / 100)
  const color = pass ? 'var(--color-correct-strong)' : 'var(--color-wrong-strong)'

  return (
    <div className="relative mx-auto h-32 w-32">
      <svg viewBox="0 0 128 128" className="h-32 w-32 -rotate-90">
        <circle cx="64" cy="64" r={radius} fill="none" stroke="var(--color-border)" strokeWidth={stroke} />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-3xl font-bold tabular-nums ${pass ? 'text-correct' : 'text-wrong'}`}>{score}</span>
        <span className="text-caption text-text-light">分</span>
      </div>
    </div>
  )
}

const answerOptions = ['A', 'B', 'C', 'D'] as const

function ReferenceAnswerBlock({ reference }: { reference: ExamReferenceAnswer }) {
  return (
    <section className="mt-3 border-t border-border pt-3">
      <h3 className="mb-2 text-meta font-semibold text-primary">參考答案</h3>
      <div className="rounded-lg bg-answered-soft px-3 py-3 text-reading text-app-text content-justify">
        {reference.reference_answer}
      </div>

      {reference.option_analysis && (
        <div className="mt-3">
          <h3 className="mb-1 text-meta font-semibold text-text-light">選項解析</h3>
          <div className="space-y-1.5 text-body text-app-text">
            {answerOptions.map((option) => {
              const analysis = reference.option_analysis?.[option]
              if (!analysis) return null
              return (
                <div key={option} className="grid grid-cols-[1.75rem_1fr] gap-2">
                  <span className={option === reference.answer ? 'font-semibold text-correct' : 'font-semibold text-text-light'}>
                    {option}.
                  </span>
                  <span>{analysis}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {(reference.key_concepts?.length || reference.citations?.length) && (
        <div className="mt-3 flex flex-wrap gap-2 text-caption text-text-light">
          {reference.key_concepts?.map((concept) => (
            <Badge key={concept} wrap>
              {concept}
            </Badge>
          ))}
          {reference.citations?.slice(0, 3).map((citation, index) => (
            <Badge
              key={`${citation.guide_key}-${citation.node_id}-${index}`}
              tone="accent"
              wrap
              title={citation.why_relevant}
            >
              {citation.title}
              {citation.page_label ? ` · ${citation.page_label}` : ''}
            </Badge>
          ))}
        </div>
      )}
    </section>
  )
}

export default function ExamResults({ onRetry }: ExamResultsProps) {
  const examData = useExamStore((s) => s.examData)!
  const examKey = useExamStore((s) => s.examKey)
  const userAnswers = useExamStore((s) => s.userAnswers)
  const [referencesByQuestion, setReferencesByQuestion] = useState<Record<string, ExamReferenceAnswer>>({})
  const scoreHeadingRef = useRef<HTMLHeadingElement>(null)

  // 交卷後從頁首開始看成績；焦點移到成績標題，讓螢幕報讀器直接念出分數。
  useEffect(() => {
    scrollMainToTop()
    scoreHeadingRef.current?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    let active = true
    loadReferenceAnswers(examKey)
      .then((references) => {
        if (active) setReferencesByQuestion(references ?? {})
      })
      .catch((error) => {
        console.warn(`[examReferenceAnswers] 載入失敗 ${examKey}`, error)
        if (active) setReferencesByQuestion({})
      })

    return () => {
      active = false
    }
  }, [examKey])

  let correct = 0, wrong = 0, skipped = 0
  examData.questions.forEach((q) => {
    if (userAnswers[q.id] === q.answer) correct++
    else if (userAnswers[q.id]) wrong++
    else skipped++
  })

  const total = examData.questions.length
  const score = Math.round((correct / total) * 100)
  const pass = score >= examData.passing_score
  const renderImage = (image: QuestionImage) => (
    <div className="w-full overflow-hidden bg-white" style={{ aspectRatio: imageAspectRatio(image) }}>
      <img
        src={publicAsset(image.src)}
        alt={image.alt}
        loading="eager"
        decoding="async"
        className="block h-full w-full object-contain"
      />
    </div>
  )
  const renderImageAsset = (image: QuestionImage) => {
    if (!image.markdown) return renderImage(image)

    return (
      <div>
        <div className="border-b border-border bg-app-bg">
          <div className="px-3 py-2 text-caption font-semibold text-text-light">
            {image.markdown_title ?? '程式碼'}
          </div>
          <CodeSnippet code={image.markdown} language={image.markdown_language} />
        </div>
        <details className="bg-white">
          <summary className="cursor-pointer px-3 py-2 text-caption text-text-light hover:text-primary">
            查看原始截圖
          </summary>
          {renderImage(image)}
        </details>
      </div>
    )
  }

  const wrongIndices = examData.questions
    .map((q, i) => ({ q, i }))
    .filter(({ q }) => userAnswers[q.id] && userAnswers[q.id] !== q.answer)
    .map(({ i }) => i)

  const jumpToQuestion = (i: number) => {
    document.getElementById(`result-q-${i}`)?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'start' })
  }

  return (
    <div className="page-shell">
      {/* 成績頁唯一的 <h1>；交卷後焦點移到這裡（id 是 test_exam_flow 的焦點目標）。 */}
      <PageHeader
        className="mb-4"
        eyebrow={examData.exam}
        titleId="exam-score-heading"
        titleRef={scoreHeadingRef}
        titleTabIndex={-1}
        title={
          <>
            考試成績
            <span className="sr-only">：{score} 分，{pass ? '已達及格標準' : '尚未達及格標準'}</span>
          </>
        }
      />
      <section className="surface mb-6 p-4 text-center sm:p-6" aria-label="成績摘要">
        <ScoreRing score={score} pass={pass} />
        <div
          className={`mt-3 inline-block rounded-full border px-4 py-1 text-ui font-semibold ${
            pass ? 'border-correct-line bg-correct-soft text-correct' : 'border-wrong-line bg-wrong-soft text-wrong'
          }`}
        >
          {pass ? '已達及格標準' : '尚未達及格標準'}
        </div>
        <div className="flex gap-3 flex-wrap justify-center my-6">
          <StatBox value={correct} label="答對" valueColor="text-correct" />
          <StatBox value={wrong} label="答錯" valueColor="text-wrong" />
          <StatBox value={skipped} label="未答" valueColor="text-text-light" />
          <StatBox value={total} label="總題數" />
        </div>
        <ProgressBar
          percent={score}
          color={pass ? 'bg-correct-strong' : 'bg-wrong-strong'}
          height="h-3"
        />
        <div className="mt-2 text-meta text-text-light">及格線：{examData.passing_score} 分</div>

        {wrongIndices.length > 0 && (
          <div className="mt-6 text-left">
            <h2 id="wrong-jump-label" className="mb-2 text-center text-meta font-semibold text-text-light">
              錯題快速跳轉
            </h2>
            <div className="flex flex-wrap justify-center gap-2" role="group" aria-labelledby="wrong-jump-label">
              {wrongIndices.map((i) => (
                <Chip key={i} tone="wrong" onClick={() => jumpToQuestion(i)}>
                  第 {i + 1} 題
                </Chip>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6">
          <button type="button" className="btn-outline" onClick={onRetry}>
            重新考試
          </button>
        </div>
      </section>

      <h2 className="section-title mb-4">詳細解析</h2>
      {examData.questions.map((q, i) => {
        const ua = userAnswers[q.id]
        const isCorrect = ua === q.answer
        const isSkipped = !ua
        const reference = referenceForQuestion(referencesByQuestion, examKey, q.id)
        const contextImages = q.images?.filter((image) => image.placement === 'context') ?? []
        const questionImages = q.images?.filter((image) => image.placement !== 'option' && image.placement !== 'context') ?? []
        const optionImages = q.images?.filter((image) => image.placement === 'option') ?? []
        return (
          <div
            key={q.id}
            id={`result-q-${i}`}
            className={`surface p-5 mb-3 scroll-mt-4 ${
              isCorrect ? 'border-correct-line' : isSkipped ? 'border-border' : 'border-wrong-line'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-meta font-semibold text-text-light">第 {i + 1} 題</h3>
              <Badge tone={isCorrect ? 'correct' : isSkipped ? 'warning' : 'wrong'}>
                {isCorrect ? '正確' : isSkipped ? '未作答' : '錯誤'}
              </Badge>
            </div>
            {q.context && (
              <div className="mb-3 rounded-lg border border-answered-line/60 bg-answered-soft px-4 py-3 text-body text-app-text">
                {q.context}
              </div>
            )}
            {contextImages.length > 0 && (
              <div className="grid grid-cols-1 gap-3 mb-3">
                {contextImages.map((image) => (
                  <figure
                    key={`${q.id}-${image.src}`}
                    className="rounded-lg border border-border bg-white overflow-hidden"
                  >
                    {renderImageAsset(image)}
                    <figcaption className="px-3 py-2 text-caption text-text-light border-t border-border">
                      PDF 第 {image.page_number} 頁題組附圖
                    </figcaption>
                  </figure>
                ))}
              </div>
            )}
            {q.context_blocks?.map((block, blockIndex) => (
              <div
                key={`${q.id}-context-block-${blockIndex}`}
                className="mb-3 overflow-hidden rounded-lg border border-border bg-white"
              >
                {block.title && (
                  <div className="border-b border-border bg-app-bg px-3 py-2 text-caption font-semibold text-text-light">
                    {block.title}
                  </div>
                )}
                <CodeSnippet code={block.markdown} language={block.language} />
              </div>
            ))}
            <div className="mb-3 text-reading text-app-text content-justify">{q.question}</div>
            {questionImages.length > 0 && (
              <div className="grid grid-cols-1 gap-3 mb-3">
                {questionImages.map((image) => (
                  <figure
                    key={`${q.id}-${image.src}`}
                    className="rounded-lg border border-border bg-white overflow-hidden"
                  >
                    {renderImageAsset(image)}
                    <figcaption className="px-3 py-2 text-caption text-text-light border-t border-border">
                      PDF 第 {image.page_number} 頁{image.type === 'page' ? '原頁截圖' : '題目附圖'}
                    </figcaption>
                  </figure>
                ))}
              </div>
            )}
            <div className="space-y-1 text-body">
              {!isCorrect && !isSkipped && (
                <div className="text-wrong">
                  您的答案：({ua}) {q.options[ua!]}
                  {optionImages
                    .filter((image) => image.option === ua)
                    .map((image) => (
                      <div
                        key={`${q.id}-${ua}-${image.src}`}
                        className="mt-2 rounded-md border border-border bg-white"
                      >
                        {renderImageAsset(image)}
                      </div>
                    ))}
                </div>
              )}
              <div className="text-correct">
                正確答案：({q.answer}) {q.options[q.answer]}
                {optionImages
                  .filter((image) => image.option === q.answer)
                  .map((image) => (
                    <div
                      key={`${q.id}-${q.answer}-${image.src}`}
                      className="mt-2 rounded-md border border-border bg-white"
                    >
                      {renderImageAsset(image)}
                    </div>
                  ))}
              </div>
            </div>
            {q.explanation && (
              <div className="mt-3 rounded-lg bg-app-bg p-3 text-reading text-app-text content-justify">
                {q.explanation}
              </div>
            )}
            {reference && <ReferenceAnswerBlock reference={reference} />}
          </div>
        )
      })}
    </div>
  )
}
