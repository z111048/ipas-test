import { useExamStore } from '../../store/examStore'
import type { Question, QuestionImage } from '../../types'
import { publicAsset } from '../../utils/assets'
import CodeSnippet from './CodeSnippet'

interface ExamQuestionProps {
  question: Question
  index: number
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

export default function ExamQuestion({ question, index }: ExamQuestionProps) {
  const selected = useExamStore((s) => s.userAnswers[index])
  const selectAnswer = useExamStore((s) => s.selectAnswer)
  const contextImages = question.images?.filter((image) => image.placement === 'context') ?? []
  const questionImages = question.images?.filter((image) => image.placement !== 'option' && image.placement !== 'context') ?? []
  const optionImages = question.images?.filter((image) => image.placement === 'option') ?? []
  const renderImage = (image: QuestionImage, className = '') => (
    <div
      className={`w-full overflow-hidden bg-white ${className}`}
      style={{ aspectRatio: imageAspectRatio(image) }}
    >
      <img
        src={publicAsset(image.src)}
        alt={image.alt}
        loading="eager"
        decoding="async"
        className="block h-full w-full object-contain"
      />
    </div>
  )
  const renderImageAsset = (image: QuestionImage, className = '') => {
    if (!image.markdown) return renderImage(image, className)

    return (
      <div className={className}>
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
    <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
      <div className="text-[0.78rem] text-text-light font-semibold mb-2 uppercase tracking-wide">
        第 {index + 1} 題
      </div>
      {question.context && (
        <div className="mb-4 rounded-lg border border-[#d7e7f5] bg-[#f4f9fd] px-4 py-3 text-[0.9rem] leading-relaxed text-app-text">
          {question.context}
        </div>
      )}
      {contextImages.length > 0 && (
        <div className="grid grid-cols-1 gap-3 mb-4">
          {contextImages.map((image) => (
            <figure
              key={`${image.src}-${image.page_index}`}
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
      {question.context_blocks?.map((block, blockIndex) => (
        <div
          key={`${question.id}-context-block-${blockIndex}`}
          className="mb-4 overflow-hidden rounded-lg border border-border bg-white"
        >
          {block.title && (
            <div className="border-b border-border bg-[#f8fafc] px-3 py-2 text-[0.75rem] font-semibold text-text-light">
              {block.title}
            </div>
          )}
          <CodeSnippet code={block.markdown} language={block.language} />
        </div>
      ))}
      <div className="text-[0.95rem] leading-relaxed mb-4 text-app-text">{question.question}</div>
      {questionImages.length > 0 && (
        <div className="grid grid-cols-1 gap-3 mb-4">
          {questionImages.map((image) => (
            <figure
              key={`${image.src}-${image.page_index}`}
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
      <div className="flex flex-col gap-2">
        {(['A', 'B', 'C', 'D'] as const).map((key) => (
          <label
            key={key}
            className={`flex items-start gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors text-[0.9rem] ${
              selected === key
                ? 'bg-[#eef5ff] border-accent text-primary'
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
            <span className="min-w-0 flex-1">
              <span>({key}) {question.options[key]}</span>
              {optionImages
                .filter((image) => image.option === key)
                .map((image) => (
                  <div
                    key={`${image.src}-${key}`}
                    className="mt-3 rounded-md border border-border bg-white"
                  >
                    {renderImageAsset(image)}
                  </div>
                ))}
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}
