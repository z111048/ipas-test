import { useExamStore } from '../../store/examStore'
import type { Question, QuestionImage } from '../../types'
import { publicAsset } from '../../utils/assets'
import { ChoiceOption } from '../ui'
import CodeSnippet from './CodeSnippet'

interface ExamQuestionProps {
  question: Question
  index: number
  isActive?: boolean
  registerRef?: (el: HTMLElement | null) => void
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

export default function ExamQuestion({ question, index, isActive, registerRef }: ExamQuestionProps) {
  const selected = useExamStore((s) => s.userAnswers[question.id])
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

  return (
    <article
      ref={registerRef}
      data-q-index={index}
      className={`surface p-5 mb-4 transition-shadow duration-150 ${isActive ? 'ring-2 ring-accent/50' : ''}`}
    >
      <h2 id={`exam-q-${index}-label`} className="eyebrow mb-2">
        第 {index + 1} 題
      </h2>
      {question.context && (
        <div className="mb-4 rounded-lg border border-answered-line/60 bg-answered-soft px-4 py-3 text-body text-app-text">
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
              <figcaption className="px-3 py-2 text-caption text-text-light border-t border-border">
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
            <div className="border-b border-border bg-app-bg px-3 py-2 text-caption font-semibold text-text-light">
              {block.title}
            </div>
          )}
          <CodeSnippet code={block.markdown} language={block.language} />
        </div>
      ))}
      <div className="text-reading mb-4 text-app-text content-justify">{question.question}</div>
      {questionImages.length > 0 && (
        <div className="grid grid-cols-1 gap-3 mb-4">
          {questionImages.map((image) => (
            <figure
              key={`${image.src}-${image.page_index}`}
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
      <div
        role="radiogroup"
        aria-labelledby={`exam-q-${index}-label`}
        className="flex flex-col gap-2"
      >
        {(['A', 'B', 'C', 'D'] as const).map((key) => {
          const images = optionImages.filter((image) => image.option === key)
          return (
            <ChoiceOption
              key={key}
              kind="radio"
              letter={key}
              name={`q${index}`}
              value={key}
              checked={selected === key}
              // 只在 radio 的 onChange 作答：點 <label> 會由瀏覽器轉成對 radio 的 click，
              // 若 label 也掛 onClick，一次點擊會呼叫兩次 selectAnswer。
              // 鍵盤（Space、上下方向鍵）同樣走 onChange。ChoiceOption 已照此實作。
              onChange={(value) => selectAnswer(question.id, value as typeof key)}
              after={
                images.length > 0
                  ? images.map((image) => (
                      <div key={`${image.src}-${key}`} className="mt-3 rounded-md border border-border bg-white">
                        {renderImageAsset(image)}
                      </div>
                    ))
                  : undefined
              }
            >
              {question.options[key]}
            </ChoiceOption>
          )
        })}
      </div>
    </article>
  )
}
