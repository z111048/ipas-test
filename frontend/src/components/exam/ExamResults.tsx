import { useExamStore } from '../../store/examStore'
import type { QuestionImage } from '../../types'
import ProgressBar from '../shared/ProgressBar'
import StatBox from '../shared/StatBox'
import { publicAsset } from '../../utils/assets'
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

export default function ExamResults({ onRetry }: ExamResultsProps) {
  const examData = useExamStore((s) => s.examData)!
  const userAnswers = useExamStore((s) => s.userAnswers)

  let correct = 0, wrong = 0, skipped = 0
  examData.questions.forEach((q, i) => {
    if (userAnswers[i] === q.answer) correct++
    else if (userAnswers[i]) wrong++
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
        <div className="border-b border-border bg-[#f8fafc]">
          <div className="px-3 py-2 text-[0.75rem] font-semibold text-text-light">
            {image.markdown_title ?? '程式碼'}
          </div>
          <CodeSnippet code={image.markdown} language={image.markdown_language} />
        </div>
        <details className="bg-white">
          <summary className="cursor-pointer px-3 py-2 text-[0.75rem] text-text-light hover:text-primary">
            查看原始截圖
          </summary>
          {renderImage(image)}
        </details>
      </div>
    )
  }

  return (
    <div>
      <div className="bg-card rounded-xl shadow-sm border border-border p-8 text-center mb-6">
        <div className="text-text-light mb-2">{examData.exam}</div>
        <div className={`text-6xl font-bold mb-2 ${pass ? 'text-success' : 'text-error'}`}>
          {score} 分
        </div>
        <div className="text-lg mb-6">{pass ? '🎉 恭喜通過！' : '❌ 尚未通過，繼續加油！'}</div>
        <div className="flex gap-3 flex-wrap justify-center mb-6">
          <StatBox value={correct} label="答對" valueColor="text-success" />
          <StatBox value={wrong} label="答錯" valueColor="text-error" />
          <StatBox value={skipped} label="未答" valueColor="text-text-light" />
          <StatBox value={total} label="總題數" />
        </div>
        <ProgressBar
          percent={score}
          color={pass ? 'bg-success' : 'bg-error'}
          height="h-3"
        />
        <div className="text-[0.8rem] text-text-light mt-2">及格線：{examData.passing_score} 分</div>
        <button
          className="mt-6 border border-accent text-accent rounded-lg px-6 py-2 text-[0.88rem] hover:bg-accent hover:text-white transition-colors cursor-pointer bg-transparent"
          onClick={onRetry}
        >
          重新考試
        </button>
      </div>

      <h2 className="text-lg font-semibold text-primary mb-4">📝 詳細解析</h2>
      {examData.questions.map((q, i) => {
        const ua = userAnswers[i]
        const isCorrect = ua === q.answer
        const isSkipped = !ua
        const contextImages = q.images?.filter((image) => image.placement === 'context') ?? []
        const questionImages = q.images?.filter((image) => image.placement !== 'option' && image.placement !== 'context') ?? []
        const optionImages = q.images?.filter((image) => image.placement === 'option') ?? []
        return (
          <div
            key={q.id}
            className={`bg-card rounded-xl border p-5 mb-3 ${
              isCorrect ? 'border-success/30' : isSkipped ? 'border-border' : 'border-error/30'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[0.78rem] text-text-light font-semibold uppercase tracking-wide">
                第 {i + 1} 題
              </span>
              <span
                className={`text-[0.75rem] px-2 py-0.5 rounded-full font-medium ${
                  isCorrect
                    ? 'bg-[#eafaf1] text-success'
                    : isSkipped
                      ? 'bg-[#fef5e7] text-warning'
                      : 'bg-[#fdf2f2] text-error'
                }`}
              >
                {isCorrect ? '✓ 正確' : isSkipped ? '— 未作答' : '✗ 錯誤'}
              </span>
            </div>
            {q.context && (
              <div className="mb-3 rounded-lg border border-[#d7e7f5] bg-[#f4f9fd] px-4 py-3 text-[0.88rem] leading-relaxed text-app-text">
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
                    <figcaption className="px-3 py-2 text-[0.75rem] text-text-light border-t border-border">
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
                  <div className="border-b border-border bg-[#f8fafc] px-3 py-2 text-[0.75rem] font-semibold text-text-light">
                    {block.title}
                  </div>
                )}
                <CodeSnippet code={block.markdown} language={block.language} />
              </div>
            ))}
            <div className="text-[0.92rem] mb-3 text-app-text">{q.question}</div>
            {questionImages.length > 0 && (
              <div className="grid grid-cols-1 gap-3 mb-3">
                {questionImages.map((image) => (
                  <figure
                    key={`${q.id}-${image.src}`}
                    className="rounded-lg border border-border bg-white overflow-hidden"
                  >
                    {renderImageAsset(image)}
                    <figcaption className="px-3 py-2 text-[0.75rem] text-text-light border-t border-border">
                      PDF 第 {image.page_number} 頁{image.type === 'page' ? '原頁截圖' : '題目附圖'}
                    </figcaption>
                  </figure>
                ))}
              </div>
            )}
            <div className="text-[0.85rem] space-y-1">
              {!isCorrect && !isSkipped && (
                <div className="text-error">
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
              <div className="text-success">
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
              <div className="mt-3 bg-[#f8f9fa] rounded-lg p-3 text-[0.85rem] text-text-light leading-relaxed">
                {q.explanation}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
