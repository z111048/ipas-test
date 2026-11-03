import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useExamStore } from '../../store/examStore'
import type { ExamReferenceAnswer, Question, QuestionImage } from '../../types'
import { loadReferenceAnswers, referenceForQuestion } from '../../data/referenceAnswerLoaders'
import ProgressBar from '../shared/ProgressBar'
import StatBox from '../shared/StatBox'
import { publicAsset } from '../../utils/assets'
import { preferredScrollBehavior } from '../../utils/motion'
import { MAIN_SCROLL_CONTAINER_ID, scrollMainToTop } from '../../utils/scrollMain'
import { Badge, Chip, ChipGroup, PageHeader, StatePanel } from '../ui'
import CodeSnippet from './CodeSnippet'
import { citationRoute, examSubjectId, relatedPracticeTarget } from './examResultLinks'
import {
  consumeResultsAnchor,
  readResultsView,
  writeResultsView,
  type ExamResultsReturnState,
  type ResultFilter,
} from './resultsViewState'

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

/** 教材頁碼（如 3-33）讀起來像內部代號：統一寫成「第 3-33 頁」；本身已帶「頁」字的保留原樣。 */
function formatPageLabel(pageLabel: string) {
  const trimmed = pageLabel.trim()
  return trimmed.endsWith('頁') ? trimmed : `第 ${trimmed} 頁`
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

/**
 * 官方解析只有「正確答案為(X)。」時，與上方「正確答案」那行完全重複，不另外顯示。
 * 其他內容（含來源勘誤說明）照原文顯示。
 */
const RESTATED_ANSWER = /^\s*正確答案(?:為|是)?\s*[:：]?\s*[（(]?\s*[A-D]\s*[)）]?\s*[。.]?\s*$/

function withMeaningfulExplanation(question: Question): Question {
  return RESTATED_ANSWER.test(question.explanation ?? '') ? { ...question, explanation: '' } : question
}

/** 參考答案依原文的空行／換行分段，不增刪文字。 */
function paragraphs(text: string) {
  return text
    .split(/\n\s*\n|\n/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function ReferenceAnswerBlock({
  reference,
  subjectId,
  returnState,
  onCitationNavigate,
}: {
  reference: ExamReferenceAnswer
  subjectId: string | null
  returnState: ExamResultsReturnState
  onCitationNavigate: (to: string) => void
}) {
  const answerParagraphs = paragraphs(reference.reference_answer)
  return (
    <section className="mt-3 border-t border-border pt-3">
      <h3 className="mb-2 text-meta font-semibold text-primary">參考答案</h3>
      <div className="space-y-2 rounded-lg bg-panel px-3 py-3 text-reading text-app-text content-justify">
        {answerParagraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
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

      {Boolean(reference.key_concepts?.length) && (
        <div className="mt-3 flex flex-wrap gap-2 text-caption text-text-light">
          {reference.key_concepts?.map((concept) => (
            <Badge key={concept} wrap>
              {concept}
            </Badge>
          ))}
        </div>
      )}

      {Boolean(reference.citations?.length) && (
        <div className="mt-3">
          <h3 className="mb-1 text-meta font-semibold text-text-light">學習指引對應段落</h3>
          <div className="flex flex-wrap gap-2">
            {reference.citations?.slice(0, 3).map((citation, index) => {
              const label = `${citation.title}${citation.page_label ? `・${formatPageLabel(citation.page_label)}` : ''}`
              const to = citationRoute(citation, subjectId)
              const key = `${citation.guide_key}-${citation.node_id}-${index}`
              return to ? (
                <Chip
                  key={key}
                  to={to}
                  state={returnState}
                  title={citation.why_relevant}
                  onClick={() => onCitationNavigate(to)}
                >
                  {label}
                </Chip>
              ) : (
                <Badge key={key} tone="accent" wrap title={citation.why_relevant}>
                  {label}
                </Badge>
              )
            })}
          </div>
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
  const location = useLocation()
  // 從學習指引回來（上一頁或「回到考試成績」）時沿用離開前的篩選、展開與捲動位置
  const [restored] = useState(() => readResultsView(examKey, userAnswers))
  const [filter, setFilter] = useState<ResultFilter>(() => restored?.filter ?? 'all')
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => restored?.expanded ?? new Set())
  const [referencesLoaded, setReferencesLoaded] = useState(false)
  const pendingAnchorRef = useRef(restored?.anchor ?? null)
  const scoreHeadingRef = useRef<HTMLHeadingElement>(null)
  const subjectId = examSubjectId(examKey)
  const returnState: ExamResultsReturnState = { examResultsReturn: { to: location.pathname } }

  // 交卷後從頁首開始看成績；焦點移到成績標題，讓螢幕報讀器直接念出分數。
  // 從引用連結回來時改由下方的錨點還原處理。
  useEffect(() => {
    if (pendingAnchorRef.current) return
    scrollMainToTop()
    scoreHeadingRef.current?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    if (!examKey) return
    writeResultsView({
      examKey,
      answers: userAnswers,
      filter,
      expanded,
      anchor: readResultsView(examKey, userAnswers)?.anchor ?? null,
    })
  }, [examKey, userAnswers, filter, expanded])

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
      .finally(() => {
        if (active) setReferencesLoaded(true)
      })

    return () => {
      active = false
    }
  }, [examKey])

  // 參考詳解載入後（展開的解析高度才確定）把離開前那一題對齊回原位，焦點還給原本點的引用連結。
  useEffect(() => {
    const anchor = pendingAnchorRef.current
    if (!anchor || !referencesLoaded) return
    pendingAnchorRef.current = null
    consumeResultsAnchor()
    const frame = requestAnimationFrame(() => {
      const main = document.getElementById(MAIN_SCROLL_CONTAINER_ID)
      const card = document.getElementById(`result-q-${anchor.questionIndex}`)
      if (!main || !card) {
        scrollMainToTop()
        scoreHeadingRef.current?.focus({ preventScroll: true })
        return
      }
      const delta = card.getBoundingClientRect().top - main.getBoundingClientRect().top - anchor.offset
      main.scrollTo({ top: main.scrollTop + delta, left: 0, behavior: 'instant' })
      const link = anchor.to
        ? Array.from(card.querySelectorAll<HTMLAnchorElement>('a[href]')).find((a) =>
            a.getAttribute('href')?.endsWith(anchor.to!),
          )
        : undefined
      ;(link ?? card).focus({ preventScroll: true })
    })
    return () => cancelAnimationFrame(frame)
  }, [referencesLoaded])

  const rememberCitationOrigin = (questionIndex: number, to: string) => {
    if (!examKey) return
    const main = document.getElementById(MAIN_SCROLL_CONTAINER_ID)
    const card = document.getElementById(`result-q-${questionIndex}`)
    const offset = main && card ? card.getBoundingClientRect().top - main.getBoundingClientRect().top : 0
    writeResultsView({ examKey, answers: userAnswers, filter, expanded, anchor: { questionIndex, offset, to } })
  }

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

  const results = examData.questions.map((rawQuestion, i) => {
    const q = withMeaningfulExplanation(rawQuestion)
    const ua = userAnswers[q.id]
    const reference = referenceForQuestion(referencesByQuestion, examKey, q.id)
    return {
      q,
      i,
      ua,
      isCorrect: ua === q.answer,
      isSkipped: !ua,
      reference,
      hasExplanation: Boolean(q.explanation) || Boolean(reference),
    }
  })

  const wrongIndices = results.filter((r) => !r.isCorrect && !r.isSkipped).map((r) => r.i)
  const visibleResults = results.filter((r) =>
    filter === 'wrong' ? !r.isCorrect && !r.isSkipped : filter === 'skipped' ? r.isSkipped : true,
  )
  const expandableVisible = visibleResults.filter((r) => r.hasExplanation)
  const allVisibleExpanded = expandableVisible.length > 0 && expandableVisible.every((r) => expanded.has(r.q.id))

  // 「下一步」的章節：以答錯題（沒有答錯就用未答題）的參考詳解引用推出最相關的章節練習
  const missedResults = results.filter((r) => !r.isCorrect && !r.isSkipped)
  const nextStepBasis = missedResults.length > 0 ? missedResults : results.filter((r) => r.isSkipped)
  const nextStep = relatedPracticeTarget(nextStepBasis.map((r) => r.reference?.citations ?? []), subjectId)

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAllVisible = () => {
    setExpanded((prev) => {
      const next = new Set(prev)
      for (const r of expandableVisible) {
        if (allVisibleExpanded) next.delete(r.q.id)
        else next.add(r.q.id)
      }
      return next
    })
  }

  const jumpToQuestion = (i: number) => {
    const id = examData.questions[i]?.id
    if (filter === 'skipped') setFilter('all')
    if (id) setExpanded((prev) => (prev.has(id) ? prev : new Set(prev).add(id)))
    // 等篩選與展開的版面更新後再捲
    requestAnimationFrame(() => {
      document.getElementById(`result-q-${i}`)?.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'start' })
    })
  }

  const filterOptions: Array<{ id: ResultFilter; label: string; count: number }> = [
    { id: 'all', label: '全部', count: total },
    { id: 'wrong', label: '答錯', count: wrong },
    { id: 'skipped', label: '未答', count: skipped },
  ]

  return (
    <div className="page-shell">
      <div className="mx-auto w-full max-w-[46rem]">
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
            <StatBox tone="muted" value={correct} label="答對" valueColor="text-correct" />
            <StatBox tone="muted" value={wrong} label="答錯" valueColor="text-wrong" />
            <StatBox tone="muted" value={skipped} label="未答" valueColor="text-text-light" />
            <StatBox tone="muted" value={total} label="總題數" />
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
              重新作答
            </button>
          </div>
        </section>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="section-title mb-2">詳細解析</h2>
            <ChipGroup label="篩選題目" labelHidden>
              {filterOptions.map((option) => (
                <Chip
                  key={option.id}
                  active={filter === option.id}
                  count={option.count}
                  disabled={option.id !== 'all' && option.count === 0}
                  onClick={() => setFilter(option.id)}
                >
                  {option.label}
                </Chip>
              ))}
            </ChipGroup>
          </div>
          {expandableVisible.length > 0 && (
            <button
              type="button"
              className="btn-ghost self-start sm:self-auto"
              onClick={toggleAllVisible}
              aria-pressed={allVisibleExpanded}
            >
              {allVisibleExpanded ? '全部收合解析' : '全部展開解析'}
            </button>
          )}
        </div>

        {visibleResults.length === 0 && (
          <StatePanel className="mb-4">
            {filter === 'wrong' ? '這次沒有答錯的題目。' : '這次沒有未作答的題目。'}
          </StatePanel>
        )}

        {visibleResults.map(({ q, i, ua, isCorrect, isSkipped, reference, hasExplanation }) => {
          const contextImages = q.images?.filter((image) => image.placement === 'context') ?? []
          const questionImages = q.images?.filter((image) => image.placement !== 'option' && image.placement !== 'context') ?? []
          const optionImages = q.images?.filter((image) => image.placement === 'option') ?? []
          const isOpen = expanded.has(q.id)
          const explanationId = `result-q-${i}-explanation`
          return (
            <div
              key={q.id}
              id={`result-q-${i}`}
              tabIndex={-1}
              className={`surface status-card p-4 pl-5 sm:p-5 sm:pl-6 mb-3 scroll-mt-4 ${
                isCorrect ? 'status-card-correct' : isSkipped ? 'status-card-skipped' : 'status-card-wrong'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-meta font-semibold text-text-light">第 {i + 1} 題</h3>
                <Badge tone={isCorrect ? 'correct' : isSkipped ? 'unanswered' : 'wrong'}>
                  {isCorrect ? '正確' : isSkipped ? '未作答' : '錯誤'}
                </Badge>
              </div>
              {q.context && (
                <div className="mb-3 rounded-lg bg-panel px-4 py-3 text-body text-app-text">
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
              {hasExplanation && (
                <button
                  type="button"
                  className="btn-ghost btn-sm mt-3 -ml-2"
                  onClick={() => toggleExpanded(q.id)}
                  aria-expanded={isOpen}
                  aria-controls={explanationId}
                >
                  {isOpen ? '收起解析' : '看解析'}
                </button>
              )}
              {isOpen && (
                <div id={explanationId}>
                  {q.explanation && (
                    <div className="mt-3 rounded-lg bg-app-bg p-3 text-reading text-app-text content-justify">
                      {q.explanation}
                    </div>
                  )}
                  {reference && (
                    <ReferenceAnswerBlock
                      reference={reference}
                      subjectId={subjectId}
                      returnState={returnState}
                      onCitationNavigate={(to) => rememberCitationOrigin(i, to)}
                    />
                  )}
                </div>
              )}
            </div>
          )
        })}

        <section className="surface mt-6 p-4 sm:p-5" aria-labelledby="exam-next-step-heading">
          <h2 id="exam-next-step-heading" className="section-title">下一步</h2>
          <p className="mt-1 text-body text-text-light">
            {wrong + skipped === 0
              ? '這份考卷全部答對，可以換一份考卷或回到章節練習鞏固。'
              : `這次答錯 ${wrong} 題、未答 ${skipped} 題，建議先回到相關章節練習，再重新作答。`}
          </p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {nextStep && (
              <Link to={nextStep.to} className="btn-primary">
                {nextStep.label}
              </Link>
            )}
            <button type="button" className="btn-outline" onClick={onRetry}>
              重新作答
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
