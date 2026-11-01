import { Link, useLocation, useParams } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import type React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeRaw from 'rehype-raw'
import rehypeKatex from 'rehype-katex'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import guideHierarchyRaw from '../generated/guideHierarchy.json'
import guideImagesRaw from '../generated/guideImages.json'
import guideExamAnnotationsIndexRaw from '../generated/guideExamAnnotations/index.json'
import type { GuideHierarchyData } from '../types'
import type { ColabNotebook, GuideBlock, GuideContent, GuideExamAnnotation, GuideExamAnnotationsChapterData, GuideExamAnnotationsIndexData, GuideFormula, GuideImageAsset, GuideImagesData, GuideOutlinesData } from '../types'
import { GUIDE_NOTICES } from '../constants/guideNotices'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'
import GuideBreadcrumb from '../components/guide/GuideBreadcrumb'
import { examResultsReturnTarget } from '../components/exam/resultsViewState'
import { guideBreadcrumb } from '../data/guideNav'
import ColabSection from '../components/guide/ColabSection'
import { publicAsset } from '../utils/assets'
import { cleanExamText } from '../utils/examText'
import { preferredScrollBehavior } from '../utils/motion'
import { useScrollProgress, ReadingProgressBar, BackToTopButton } from '../components/shared/ReadingProgress'
import { MobileActionBar, PageHeader, StatePanel } from '../components/ui'
import { useMediaQuery, WIDE_LAYOUT_QUERY } from '../hooks/useMediaQuery'
import {
  MobileChapterDrawer,
  READING_LIST_ITEM_CLASS,
  READING_PARAGRAPH_CLASS,
  READING_WIDE_BOX_CLASS,
  ReadingAuxiliary,
  ReadingContent,
  ReadingLayout,
  ReadingSurface,
  ReadingToc,
} from '../components/reading'
import type { ReadingTocEntry } from '../components/reading'
import { useLearningIndex } from '../features/learning/useLearningIndex'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
const guideHierarchy = guideHierarchyRaw as unknown as GuideHierarchyData
const guideImages = guideImagesRaw as unknown as GuideImagesData
const guideExamAnnotationsIndex = guideExamAnnotationsIndexRaw as unknown as GuideExamAnnotationsIndexData
const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')
const colabNotebookModules = import.meta.glob<{ default: ColabNotebook }>('../generated/colabNotebooks/*/*.json')
const guideExamAnnotationModules = import.meta.glob<{ default: GuideExamAnnotationsChapterData }>('../generated/guideExamAnnotations/*/*.json')

function normalizeOcrSoftBreaks(text: string) {
  const structuralLine = /^(#{1,6}\s|[-*+]\s|\d+\.\s|[A-Z]\.\s|[a-z]\.\s|[|>`~])/
  const result: string[] = []
  let block: string[] = []

  const flushBlock = () => {
    if (block.length === 0) return
    if (block.some((line) => structuralLine.test(line.trim()))) {
      result.push(...block)
    } else {
      result.push(
        block
          .map((line) => line.trim())
          .join(' ')
          .replace(/([，、；：])\s+/g, '$1')
          .replace(/\s+([，。！？；：、）】])/g, '$1')
          .replace(/([（【])\s+/g, '$1'),
      )
    }
    block = []
  }

  text.split('\n').forEach((line) => {
    const trimmedRight = line.trimEnd()
    if (!trimmedRight.trim()) {
      flushBlock()
      if (result.length > 0 && result[result.length - 1] !== '') result.push('')
      return
    }
    block.push(trimmedRight)
  })
  flushBlock()
  return result.join('\n').trim()
}

function headingAnchor(title: string) {
  const slug = title
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^0-9a-z\u4e00-\u9fff-]+/g, '')
    .replace(/^-+|-+$/g, '')
  return slug || 'section'
}

function plainText(children: React.ReactNode): string {
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(plainText).join('')
  if (children && typeof children === 'object' && 'props' in children) {
    return plainText((children as React.ReactElement<{ children?: React.ReactNode }>).props.children)
  }
  return ''
}

function blockIndentStyle(depth: number, extra = 0): React.CSSProperties {
  const level = Math.max(depth - 1 + extra, 0)
  return {
    '--guide-indent-desktop': `${Math.min(level, 8) * 0.9}rem`,
    '--guide-indent-tablet': `${Math.min(level, 5) * 0.62}rem`,
    '--guide-indent-mobile': `${Math.min(level, 3) * 0.42}rem`,
  } as React.CSSProperties
}

function blockTextClass(block: GuideBlock) {
  if (block.type === 'heading') {
    if (block.depth <= 2) return 'text-lg font-bold text-primary border-b border-border pb-1 mt-6 mb-2'
    if (block.depth === 3) return 'text-base font-semibold text-accent mt-5 mb-2'
    if (block.depth === 4) return 'text-reading font-semibold text-primary mt-4 mb-1'
    if (block.depth === 5) return 'text-reading font-semibold text-app-text mt-3 mb-1'
    return 'text-body font-semibold text-text-light mt-3 mb-1'
  }
  if (block.type === 'question') return 'text-reading font-semibold text-primary bg-answered-soft border-l-4 border-accent px-3 py-2 rounded-r-lg my-3'
  if (block.type === 'answer') return 'text-reading text-app-text bg-unanswered-soft border border-border px-3 py-2 rounded-lg my-2'
  return READING_PARAGRAPH_CLASS
}

function listMarkerClass(marker?: string) {
  if (!marker) return ''
  if (/^[A-Za-z]\.$/.test(marker)) return 'min-w-[1.8rem] text-primary font-semibold'
  if (marker === '•') return 'min-w-[1.05rem] text-accent font-semibold'
  if (marker === '◦') return 'min-w-[1.05rem] text-primary/80 font-semibold'
  if (marker === '○') return 'min-w-[1.05rem] text-text-light font-semibold'
  return 'min-w-[1.05rem] text-accent font-semibold'
}

function listTextClass(marker?: string) {
  if (/^[A-Za-z]\.$/.test(marker || '')) return 'font-medium text-app-text'
  return 'text-app-text'
}

function guideHeadingDomId(blockId: string) {
  return `guide-heading-${blockId}`
}

function cssEscape(value: string) {
  if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(value)
  return value.replace(/["\\]/g, '\\$&')
}

/**
 * 從考試成績的引用連結（/guide/...#block-N）落地時標亮目標段落，讓讀者一眼找到引用處。
 * 用 Web Animations 疊在元素原本的背景之上，結束後自動回到原樣（不改 className、不殘留）。
 *
 * 分兩段：找到目標的第一刻就 `hold`（持續標亮、不淡出），因為圖片／公式／徽章撐開高度時
 * 落地 effect 還會再對齊幾次；對齊結束才 `release`，再停留一下後淡出。以前是等位置連續
 * 穩定才開始 2.5 秒動畫，實測要晚約 1 秒才亮，看起來像畫面先跳一下才標出來。
 * prefers-reduced-motion：不做漸層淡出，停留後直接消失。
 * 正文欄 overflow-x-hidden，左右外框會被裁掉，所以只往上下延伸背景。
 */
function createLandingHighlight(target: HTMLElement) {
  if (typeof target.animate !== 'function') {
    return { release: () => {}, cancel: () => {} }
  }
  const line = getComputedStyle(document.documentElement).getPropertyValue('--color-warning-line').trim() || '#f7d48b'
  const tint = `color-mix(in srgb, ${line} 45%, transparent)`
  const reduceMotion = typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const on = {
    backgroundColor: tint,
    boxShadow: `0 -4px 0 ${tint}, 0 4px 0 ${tint}`,
    borderRadius: '4px',
  }
  let hold: Animation | null = target.animate([on, on], { duration: 1, fill: 'forwards' })
  let fade: Animation | null = null
  return {
    release() {
      if (!hold) return
      // 先疊上淡出動畫再取消 hold，中間不會閃回原色。
      // 沒寫 offset 1 的關鍵影格 → 結束時回到元素自己的樣式（例如 question 區塊原本的底色）
      fade = target.animate([on, { ...on, offset: reduceMotion ? 0.99 : 0.6 }], {
        duration: reduceMotion ? 1500 : 2000,
        easing: 'ease-out',
      })
      hold.cancel()
      hold = null
    },
    cancel() {
      hold?.cancel()
      fade?.cancel()
      hold = null
      fade = null
    },
  }
}

// 表格儲存格可能夾帶 $...$ 數學式（來源是學習指引 OCR 的 <table>，例如 $\mu_1 \neq \mu_2$）。
// 沒有 $ 的儲存格走純文字，維持 whitespace-pre-line 的換行行為；有 $ 的才過 KaTeX，
// 避免對每一格都跑一次 markdown 解析。
function GuideTableCell({ text }: { text: string }) {
  if (!text.includes('$')) return <>{text}</>
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        p: ({ children }) => <span className="whitespace-pre-line">{children}</span>,
      }}
    >
      {text}
    </ReactMarkdown>
  )
}

type GuideHeadingNavEntry = ReadingTocEntry

const EXAM_NOTES_STORAGE_KEY = 'ipas.guide.showExamNotes'

function readExamNotesPreference() {
  try {
    const stored = window.localStorage.getItem(EXAM_NOTES_STORAGE_KEY)
    return stored === null ? true : stored === '1'
  } catch {
    return true
  }
}

function writeExamNotesPreference(value: boolean) {
  try {
    window.localStorage.setItem(EXAM_NOTES_STORAGE_KEY, value ? '1' : '0')
  } catch {
    // 私密視窗或封鎖網站資料時寫不進去，只影響「記住選擇」，不影響本次顯示
  }
}

/**
 * 考點標註開關。用 switch 樣式（軌道＋開／關文字）而不是實心按鈕，
 * 避免「實心藍 = 按下去才顯示」的誤讀；狀態以 role="switch" + aria-checked 表示。
 */
function ExamNotesSwitch({ checked, onToggle, className = '' }: {
  checked: boolean
  onToggle: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onToggle}
      title="在段落後顯示「考過幾題」標註"
      className={`min-h-11 items-center gap-3 rounded-lg px-2 text-ui text-app-text hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-accent lg:min-h-9 ${className}`}
    >
      <span>考點標註</span>
      <span className="inline-flex items-center gap-2">
        <span className="text-meta text-text-light" aria-hidden="true">{checked ? '開' : '關'}</span>
        <span
          aria-hidden="true"
          className={`relative inline-block h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-border'}`}
        >
          <span
            className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-[left] ${checked ? 'left-[1.125rem]' : 'left-0.5'}`}
          />
        </span>
      </span>
    </button>
  )
}

function GuideHtmlTable({ rows, html }: { rows?: string[][]; html?: string }) {
  if (html) {
    return (
      <div
        className={`guide-depth-block my-4 ${READING_WIDE_BOX_CLASS}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  }
  if (!rows?.length) return null
  const [header, ...bodyRows] = rows
  return (
    <div className={`guide-depth-block my-4 ${READING_WIDE_BOX_CLASS}`}>
      <table className="table-soft text-ui table-auto">
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th key={index} scope="col" className="whitespace-pre-line">
                <GuideTableCell text={cell} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="leading-6 whitespace-pre-line">
                  <GuideTableCell text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function blockFormulaEntries(block: GuideBlock): GuideFormula[] {
  if (block.formulas?.length) return block.formulas
  if (Array.isArray(block.latex)) return block.latex.map((latex) => ({ latex, display: true }))
  if (block.latex) return [{ latex: block.latex, display: true }]
  return []
}

function GuideFormulas({ formulas }: { formulas: GuideFormula[] }) {
  if (formulas.length === 0) return null
  return (
    <div className={`guide-formulas mt-2 space-y-1 text-reading ${READING_WIDE_BOX_CLASS}`}>
      {formulas.map((formula, index) => {
        const source = formula.display === false
          ? `$${formula.latex}$`
          : `$$\n${formula.latex}\n$$`
        return (
          <ReactMarkdown
            key={`${formula.latex}-${index}`}
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              p: ({ children }) => (
                <div className="m-0 leading-7">{children}</div>
              ),
            }}
          >
            {source}
          </ReactMarkdown>
        )
      })}
    </div>
  )
}

function GuideBlockBody({ block }: { block: GuideBlock }) {
  const formulas = blockFormulaEntries(block)
  if (formulas.length === 0) return <>{block.text}</>
  if (block.formulaOnly) return <GuideFormulas formulas={formulas} />
  return (
    <>
      {block.text && <span>{block.text}</span>}
      <GuideFormulas formulas={formulas} />
    </>
  )
}

function GuideImageFigure({ image, depth }: { image: GuideImageAsset; depth: number }) {
  const caption = image.headingPath.length > 0 ? image.headingPath.join(' › ') : image.title
  return (
    <figure
      className="guide-depth-block my-5"
      style={blockIndentStyle(depth)}
      data-guide-image-id={image.id}
    >
      <img
        src={publicAsset(image.src)}
        alt={image.title}
        loading="lazy"
        className="block w-full max-w-4xl rounded-lg border border-border bg-white object-cover"
      />
      <figcaption className="mt-2 text-meta leading-5 text-text-light">
        {caption}
      </figcaption>
    </figure>
  )
}

function GuideSourceFigure({ block }: { block: GuideBlock }) {
  if (!block.src) return null
  return (
    <figure
      className="guide-depth-block my-5"
      style={blockIndentStyle(block.depth)}
      data-guide-source-image={block.src}
    >
      <img
        src={publicAsset(block.src)}
        alt={block.alt ?? '學習指引原圖'}
        loading="lazy"
        className="block w-full max-w-4xl rounded-lg border border-border bg-white object-contain"
      />
      <figcaption className="mt-2 text-meta leading-5 text-text-light">
        PDF 原圖{block.alt ? ` · ${block.alt}` : ''}
      </figcaption>
    </figure>
  )
}

// 段落後的公告試題標註：預設收成一個小徽章（「考過 3 題」），點了才展開題目清單，
// 避免橘色區塊打斷正文閱讀。頁面層級的「顯示考點標註」可整個關掉。
function GuideExamReferenceNotes({ annotations, depth }: { annotations: GuideExamAnnotation[]; depth: number }) {
  const [open, setOpen] = useState(false)
  if (annotations.length === 0) return null
  const visibleAnnotations = annotations.slice(0, 8)
  const hiddenCount = annotations.length - visibleAnnotations.length
  const questionCount = new Set(annotations.map((annotation) => annotation.id)).size
  const examLabels = Array.from(new Set(annotations.map((annotation) => annotation.examLabel)))

  return (
    <div className="guide-depth-block -mt-2 mb-3" style={blockIndentStyle(depth)} data-guide-exam-notes="">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="inline-flex min-h-11 items-center gap-1.5 rounded-full text-left md:min-h-0"
        title={examLabels.length > 0 ? examLabels.join('、') : undefined}
      >
        <span className="badge badge-warning">考過 {questionCount} 題</span>
        <span className="text-meta text-text-light" aria-hidden="true">{open ? '收合 ▴' : '▾'}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-2 rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-ui leading-6 text-app-text">
          {visibleAnnotations.map((annotation) => (
            <div key={annotation.id} className="border-t border-warning/20 pt-2 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-center gap-2">
                <Link to={annotation.route} className="text-link">
                  {annotation.examLabel} 第 {annotation.questionNumber} 題
                </Link>
                <span className="badge badge-warning">
                  答案 {annotation.answer}
                </span>
              </div>
              <div data-exam-text className="mt-1 text-ui leading-6 text-app-text content-justify">
                {cleanExamText(annotation.question)}
              </div>
            </div>
          ))}
          {hiddenCount > 0 && (
            <div className="border-t border-warning/20 pt-2 text-meta text-text-light">
              另有 {hiddenCount} 題引用此區塊。
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function GuideBlocksRenderer({
  blocks,
  images,
  examAnnotations,
  showExamNotes,
}: {
  blocks: GuideBlock[]
  images: GuideImageAsset[]
  examAnnotations: Record<string, GuideExamAnnotation[]>
  showExamNotes: boolean
}) {
  const imagesByHeading = images.reduce<Record<string, GuideImageAsset[]>>((acc, image) => {
    if (!image.headingBlockId) return acc
    acc[image.headingBlockId] = [...(acc[image.headingBlockId] ?? []), image]
    return acc
  }, {})

  const unmatchedImages = images.filter((image) => !image.headingBlockId || !blocks.some((block) => block.id === image.headingBlockId))

  const renderWithImages = (block: GuideBlock, element: React.ReactNode) => {
    const blockImages = imagesByHeading[block.id] ?? []
    const blockAnnotations = showExamNotes ? examAnnotations[block.id] ?? [] : []
    if (blockImages.length === 0 && blockAnnotations.length === 0) return element
    return (
      <div key={`${block.id}-with-extras`}>
        {element}
        {blockImages.map((image) => (
          <GuideImageFigure key={image.id} image={image} depth={block.depth} />
        ))}
        <GuideExamReferenceNotes annotations={blockAnnotations} depth={block.depth} />
      </div>
    )
  }

  return (
    <div className="guide-blocks text-app-text">
      {unmatchedImages.map((image) => (
        <GuideImageFigure key={image.id} image={image} depth={Math.max(image.headingDepth ?? 2, 2)} />
      ))}
      {blocks.map((block) => {
        if (block.type === 'source_image') {
          return <GuideSourceFigure key={block.id} block={block} />
        }
        if (block.type === 'table' && (block.html || block.rows?.length)) {
          return renderWithImages(block, (
            <div key={block.id} style={blockIndentStyle(block.depth)}>
              <GuideHtmlTable rows={block.rows} html={block.html} />
            </div>
          ))
        }

        if (block.type === 'list_item') {
          const hasFormulas = blockFormulaEntries(block).length > 0
          if (!block.marker) {
            const Element = hasFormulas ? 'div' : 'p'
            return renderWithImages(block, (
              <Element
                key={block.id}
                id={guideHeadingDomId(block.id)}
                data-guide-block-id={block.id}
                className={`guide-depth-block ${READING_LIST_ITEM_CLASS}`}
                style={blockIndentStyle(block.depth)}
              >
                <GuideBlockBody block={block} />
              </Element>
            ))
          }
          return renderWithImages(block, (
            <div
              key={block.id}
              id={guideHeadingDomId(block.id)}
              data-guide-block-id={block.id}
              className={`guide-depth-block grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 ${READING_LIST_ITEM_CLASS}`}
              style={blockIndentStyle(block.depth)}
            >
              <span className={listMarkerClass(block.marker)}>{block.marker}</span>
              <div className={listTextClass(block.marker)}>
                <GuideBlockBody block={block} />
              </div>
            </div>
          ))
        }

        if (block.type === 'heading') {
          const Tag = (block.depth <= 2 ? 'h2' : block.depth === 3 ? 'h3' : block.depth === 4 ? 'h4' : block.depth === 5 ? 'h5' : 'h6') as keyof React.JSX.IntrinsicElements
          return renderWithImages(block, (
            <Tag
              key={block.id}
              id={guideHeadingDomId(block.anchor || block.id)}
              data-guide-block-id={block.id}
              data-guide-anchor={block.anchor}
              className={`guide-depth-block scroll-mt-4 ${blockTextClass(block)}`}
              style={blockIndentStyle(block.depth)}
            >
              {block.title}
            </Tag>
          ))
        }

        const hasFormulas = blockFormulaEntries(block).length > 0
        const textStyle = {
          ...blockIndentStyle(block.depth),
          textIndent: !hasFormulas && block.type === 'paragraph' && block.indentFirstLine ? '2em' : undefined,
        }
        if (hasFormulas) {
          return renderWithImages(block, (
            <div
              key={block.id}
              id={guideHeadingDomId(block.id)}
              data-guide-block-id={block.id}
              className={`guide-depth-block ${blockTextClass(block)}`}
              style={textStyle}
            >
              <GuideBlockBody block={block} />
            </div>
          ))
        }
        return renderWithImages(block, (
          <p
            key={block.id}
            id={guideHeadingDomId(block.id)}
            data-guide-block-id={block.id}
            className={`guide-depth-block ${blockTextClass(block)}`}
            style={textStyle}
          >
            {block.text}
          </p>
        ))
      })}
    </div>
  )
}

export default function GuidePage() {
  const { subjectId, chapterId } = useParams<{ subjectId: string; chapterId: string }>()
  const location = useLocation()
  const examResultsReturn = examResultsReturnTarget(location.state)
  const outlineGuide = subjectId ? guideOutlines.guides[subjectId] : undefined
  const chapter = chapterId && outlineGuide ? outlineGuide.nodesById[chapterId] : undefined
  const [content, setContent] = useState<GuideContent | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)
  const [examAnnotationsByBlock, setExamAnnotationsByBlock] = useState<Record<string, GuideExamAnnotation[]>>({})
  const [colabNotebook, setColabNotebook] = useState<ColabNotebook | null>(null)
  const [showDrawer, setShowDrawer] = useState(false)
  const contentScrollRef = useRef<HTMLDivElement | null>(null)
  const drawerTriggerRef = useRef<HTMLButtonElement | null>(null)
  const stickyProgressRef = useRef<HTMLDivElement | null>(null)
  const scrollToContentBlockRef = useRef<((id: string, anchor?: string, behavior?: ScrollBehavior) => HTMLElement | null) | null>(null)
  const [activeHeadingId, setActiveHeadingId] = useState<string | null>(null)
  const [showExamNotes, setShowExamNotes] = useState(readExamNotesPreference)
  const isWideLayout = useMediaQuery(WIDE_LAYOUT_QUERY)
  const toggleExamNotes = useCallback(() => {
    setShowExamNotes((value) => {
      writeExamNotesPreference(!value)
      return !value
    })
  }, [])
  const { progress: readingProgress, showBackToTop, scrollToTop } = useScrollProgress(() => contentScrollRef.current)
  const { index: learningIndex } = useLearningIndex()
  const relatedUnits = learningIndex?.units.filter((unit) =>
    unit.chapterRefs.some((ref) => ref.subjectId === subjectId && ref.chapterId === chapterId),
  ) ?? []

  useEffect(() => {
    if (contentScrollRef.current) contentScrollRef.current.scrollTop = 0
    setShowDrawer(false)
  }, [chapterId])

  useEffect(() => {
    let cancelled = false
    setContent(null)
    setContentError(null)
    if (!outlineGuide || !chapter) return

    const moduleKey = `../generated/guideContent/${outlineGuide.key}/${chapter.contentRef}`
    const loader = guideContentModules[moduleKey]
    if (!loader) {
      setContentError(`找不到內容檔：${moduleKey}`)
      return
    }

    loader()
      .then((module) => {
        if (!cancelled) setContent(module.default)
      })
      .catch((error) => {
        if (!cancelled) {
          setContentError(error instanceof Error ? error.message : 'unknown error')
        }
      })
    return () => {
      cancelled = true
    }
  }, [chapter, outlineGuide])

  useEffect(() => {
    let cancelled = false
    setExamAnnotationsByBlock({})
    if (!outlineGuide || !chapter) return

    const moduleKey = `../generated/guideExamAnnotations/${outlineGuide.key}/${chapter.id}.json`
    const loader = guideExamAnnotationModules[moduleKey]
    if (!loader) return

    loader()
      .then((module) => {
        if (!cancelled) setExamAnnotationsByBlock(module.default.blocks ?? {})
      })
      .catch((error) => {
        // 降級是對的（考題標註是附加資訊），但不要靜默：改成 runtime fetch 之後
        // 網路失敗與「這章本來就沒有標註」會長得一模一樣，沒有這行就無從診斷。
        console.warn(`[guideExamAnnotations] 載入失敗 ${moduleKey}`, error)
        if (!cancelled) setExamAnnotationsByBlock({})
      })
    return () => {
      cancelled = true
    }
  }, [chapter, outlineGuide])

  // Load Colab notebook if available (初級 and 中級)
  useEffect(() => {
    let cancelled = false
    setColabNotebook(null)
    if (!outlineGuide || !chapter) return
    const level = outlineGuide.level
    if (!level) return

    const notebookKey = `../generated/colabNotebooks/${level}/${chapter.id}.json`
    const loader = colabNotebookModules[notebookKey]
    if (!loader) return

    loader()
      .then((module) => {
        if (!cancelled) setColabNotebook(module.default)
      })
      .catch((error) => {
        // 同上：降級但不靜默。
        // 註：`generated/colabNotebooks/index.json` 已由 export_colab_metadata.py 產出，
        // 但這裡還沒改用它——存在性仍靠上面那個 build-time glob 判斷。
        // 階段 2 把資料改成 runtime fetch 時，glob 會消失，那時才必須改讀 index.json，
        // 否則「這章有沒有 notebook」會靜默失效（41/64 章有）。
        console.warn(`[colabNotebook] 載入失敗 ${notebookKey}`, error)
      })
    return () => { cancelled = true }
  }, [chapter, outlineGuide])

  // Scroll-spy: highlight the "本節階層" entry matching the heading nearest
  // the top of the visible content, so the in-page nav tracks reading position.
  useEffect(() => {
    const container = contentScrollRef.current
    if (!container || !content) return
    const headingEls = Array.from(
      container.querySelectorAll<HTMLElement>('[data-guide-block-id][data-guide-anchor]'),
    )
    if (headingEls.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const topmost = visible.reduce((a, b) => (a.boundingClientRect.top < b.boundingClientRect.top ? a : b))
        const id = topmost.target.getAttribute('data-guide-block-id')
        if (id) setActiveHeadingId(id)
      },
      { root: container, rootMargin: '0px 0px -70% 0px', threshold: [0, 1] },
    )
    headingEls.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [content, chapterId])

  // 搜尋結果與完整目錄頁用 route#anchor 連過來。HashRouter 的網址形如
  // #/guide/s1/s1c1#anchor，react-router 會把第二個 # 之後解析成 location.hash。
  // 內容是非同步載入的，要等 content 到位才找得到目標區塊；
  // scrollToContentBlock 定義在下方（提前 return 之後），所以用 ref 轉接。
  useEffect(() => {
    const anchor = decodeURIComponent(location.hash.replace(/^#/, ''))
    if (!anchor || !content) return

    // 公式（KaTeX）與圖片是載入後才撐開高度的，只捲一次會落在錯的位置——
    // 實測目標會被推到畫面外一萬多 px。所以持續盯著內容高度，每次變動就重捲一次，
    // 連續穩定或超過上限才停；使用者一旦自己動了就立刻停手。
    let cancelled = false
    let timer = 0
    let lastHeight = -1
    let stable = 0
    let landedTarget: HTMLElement | null = null
    let highlight: ReturnType<typeof createLandingHighlight> | null = null
    const deadline = performance.now() + 12000

    const finish = () => {
      cancelled = true
      window.clearTimeout(timer)
      highlight?.release()
    }
    const tick = () => {
      if (cancelled) return
      const container = contentScrollRef.current
      const height = container?.scrollHeight ?? document.documentElement.scrollHeight
      if (height !== lastHeight || !landedTarget) {
        lastHeight = height
        stable = 0
        // 第一次用平滑捲動（尊重 reduced-motion）；之後是高度變動造成的小幅修正，
        // 直接定位，避免一連串平滑捲動互相打斷造成的跳動。
        const behavior: ScrollBehavior | undefined = landedTarget ? 'auto' : undefined
        landedTarget = scrollToContentBlockRef.current?.(anchor, anchor, behavior) ?? landedTarget
      } else {
        stable += 1
      }
      // 一找到目標就標亮並保持，對齊期間不淡出
      if (landedTarget && !highlight) {
        highlight = createLandingHighlight(landedTarget)
      }
      const keepGoing = stable < 4 && performance.now() < deadline
      if (keepGoing) {
        timer = window.setTimeout(tick, 250)
      } else {
        finish()
      }
    }
    const frame = requestAnimationFrame(tick)

    // 使用者自己動了：停止對齊、開始淡出
    window.addEventListener('wheel', finish, { passive: true, once: true })
    window.addEventListener('touchstart', finish, { passive: true, once: true })
    window.addEventListener('keydown', finish, { once: true })
    return () => {
      cancelAnimationFrame(frame)
      cancelled = true
      window.clearTimeout(timer)
      highlight?.cancel()
      window.removeEventListener('wheel', finish)
      window.removeEventListener('touchstart', finish)
      window.removeEventListener('keydown', finish)
    }
  }, [location.hash, content])

  if (!outlineGuide || !chapter) {
    return (
      <div className="page-shell">
        <PageHeader
          variant="plain"
          title="找不到章節"
          description="這個章節不存在，或內容已經移動。"
          actions={<Link to="/outline" className="btn-primary">回到學習指引目錄</Link>}
        />
      </div>
    )
  }

  const body = content?.content ?? ''
  const contentBlocks = content?.blocks ?? []
  const hasBlocks = contentBlocks.length > 0
  const guideImageKey = `${outlineGuide.sourceKey ?? outlineGuide.key}:${chapter.id}`
  const chapterImages = guideImages.byChapter[guideImageKey] ?? []
  const chapterExamAnnotationSummary = guideExamAnnotationsIndex.byGuide[outlineGuide.key]?.[chapter.id]
  const loadedExamAnnotationItems = Object.values(examAnnotationsByBlock).flat()
  const loadedExamQuestionCount = new Set(loadedExamAnnotationItems.map((annotation) => annotation.id)).size
  const chapterExamQuestionCount = chapterExamAnnotationSummary?.questions ?? loadedExamQuestionCount
  const normalizedBody = normalizeOcrSoftBreaks(body)
  const isMarkdown = content?.contentFormat === 'markdown' || body.trimStart().startsWith('#') || body.trimStart().startsWith('##')
  // 沒有 blocks、也不是 markdown 的舊格式內容：以空行切段落
  const paragraphs = hasBlocks || isMarkdown ? [] : normalizedBody.split(/\n{2,}/).filter((p) => p.trim())
  const notice = chapterId ? GUIDE_NOTICES[chapterId] : undefined
  const sourcePages = content?.sourcePages ?? []
  // 「本節階層」優先用完整階層樹（guideHierarchy.json）——它是巢狀的，
  // 而且補回了 blocks 缺漏的層級（初級 s1c1 的 blocks 完全沒有「1. 人工智慧的應用領域」
  // 這一層）。階層樹沒有資料時退回原本的 blocks 邏輯。
  //
  // 由 guide_ocr 補回的標題在頁面上沒有對應的 DOM 區塊，捲不過去，
  // 所以 id 給空字串，渲染端據此顯示成不可點的分組標籤。
  const hierarchyGuide = subjectId ? guideHierarchy.guides[subjectId] : undefined
  const hierarchyHeadings = (() => {
    if (!hierarchyGuide?.nodesById[chapter.id]) return []
    const blockIdByAnchor = new Map<string, string>()
    for (const block of contentBlocks) {
      if (block.anchor && block.id) blockIdByAnchor.set(block.anchor, block.id)
    }
    const out: GuideHeadingNavEntry[] = []
    const walk = (nodeId: string) => {
      for (const childId of hierarchyGuide.nodesById[nodeId]?.childIds ?? []) {
        const node = hierarchyGuide.nodesById[childId]
        if (!node || node.kind !== 'heading') continue
        out.push({
          id: (node.anchor && blockIdByAnchor.get(node.anchor)) ?? '',
          anchor: node.anchor ?? undefined,
          level: node.headingLevel ?? node.depth,
          title: node.title,
        })
        walk(childId)
      }
    }
    walk(chapter.id)
    return out
  })()

  const contentHeadings: GuideHeadingNavEntry[] = hierarchyHeadings.length > 0
    ? hierarchyHeadings
    : hasBlocks
    ? contentBlocks
      .filter((block) => block.type === 'heading' && block.depth >= 3 && block.depth <= 5 && block.id && block.title)
      .map((block) => ({ id: block.id, anchor: block.anchor, level: block.depth, title: block.title ?? '' }))
    : content?.headings
      ?.filter((heading) => heading.level >= 3 && heading.level <= 4)
      .map((heading) => ({ ...heading, anchor: undefined as string | undefined })) ?? []
  const childChapters = chapter.children.map((childId) => outlineGuide.nodesById[childId]).filter(Boolean)
  const hasChildChapters = childChapters.length > 0
  const pageRange = `PDF 第 ${chapter.pageRange[0]}–${chapter.pageRange[1]} 頁`
  const breadcrumb = subjectId && chapterId ? guideBreadcrumb(subjectId, chapterId) : []

  // Prev/next chapters for mobile navigation bar
  const flatIds = outlineGuide.flat
  const currentFlatIndex = flatIds.indexOf(chapter.id)
  const prevChapterId = currentFlatIndex > 0 ? flatIds[currentFlatIndex - 1] : undefined
  const nextChapterId = currentFlatIndex < flatIds.length - 1 ? flatIds[currentFlatIndex + 1] : undefined
  const prevChapter = prevChapterId ? outlineGuide.nodesById[prevChapterId] : undefined
  const nextChapter = nextChapterId ? outlineGuide.nodesById[nextChapterId] : undefined


  const scrollToContentBlock = (id: string, anchor?: string, behaviorOverride?: ScrollBehavior) => {
    const behavior = behaviorOverride ?? preferredScrollBehavior()
    const container = contentScrollRef.current
    const root: ParentNode = container ?? document
    const target = root.querySelector<HTMLElement>(
      [
        `[data-guide-block-id="${cssEscape(id)}"]`,
        anchor ? `[data-guide-anchor="${cssEscape(anchor)}"]` : '',
        `#${cssEscape(guideHeadingDomId(anchor || id))}`,
        `#${cssEscape(id)}`,
      ].filter(Boolean).join(',')
    )
    if (!target) return null
    if (!container) {
      target.scrollIntoView({ behavior, block: 'start' })
      return target
    }
    const containerTop = container.getBoundingClientRect().top
    const targetTop = target.getBoundingClientRect().top
    // 捲動容器頂端有黏住的閱讀進度條，目標要落在它下面而不是被蓋住
    const stickyOffset = stickyProgressRef.current?.offsetHeight ?? 0
    const nextTop = container.scrollTop + targetTop - containerTop - stickyOffset - 12
    container.scrollTo({
      top: nextTop,
      behavior,
    })
    if (Math.abs(container.scrollTop - nextTop) > 2 && container.scrollHeight <= container.clientHeight) {
      target.scrollIntoView({ behavior, block: 'start' })
    }
    return target
  }
  scrollToContentBlockRef.current = scrollToContentBlock

  // 版面：整頁（頁首卡、麵包屑、提示框、正文）一起在同一個捲動容器裡捲動，
  // 頁首不再固定佔住手機畫面；只有網站頂列與手機底部章節列固定。
  // 桌面右側「本頁目錄」在容器內 sticky。容器用負邊距吃掉 <main> 的上方內距，
  // 讓捲動區貼齊網站頂列（<main> 在 /guide 路由不捲動，見 App.tsx）。
  return (
    <>
    <div
      ref={contentScrollRef}
      className="-mx-4 -mt-4 h-[calc(100%+1rem)] overflow-y-auto overflow-x-hidden overscroll-contain app-scroll-stable px-4 pt-4 pb-[calc(5rem+var(--app-safe-bottom))] md:-mx-6 md:-mt-6 md:h-[calc(100%+1.5rem)] md:px-6 md:pt-6 lg:pb-6"
    >
    <div className="page-shell">
      <PageHeader
        className="mb-3 sm:mb-4"
        eyebrow="學習指引"
        title={chapter.title}
        description={outlineGuide.subject}
        meta={
          <>
            <span className="pill pill-muted">{pageRange}</span>
            {chapterExamQuestionCount > 0 && (
              <span className="pill">公告試題 {chapterExamQuestionCount} 題</span>
            )}
            {!isWideLayout && chapterExamQuestionCount > 0 && (
              // 手機：頁首會隨正文捲走，開關放在章節資訊同一列，不多佔版面；抽屜內另有一份（同一個狀態）。
              <ExamNotesSwitch checked={showExamNotes} onToggle={toggleExamNotes} className="-ml-1 inline-flex" />
            )}
          </>
        }
        actions={isWideLayout && chapterExamQuestionCount > 0 && (
          <ExamNotesSwitch checked={showExamNotes} onToggle={toggleExamNotes} className="inline-flex" />
        )}
      />

      <div className="mb-2 flex flex-wrap items-center gap-x-4 sm:mb-4">
        {examResultsReturn && (
          // 從考試成績的引用連結進來時，提供回到成績頁的入口（成績頁會還原篩選與捲動位置）
          <Link
            to={examResultsReturn}
            className="text-link inline-flex min-h-11 shrink-0 items-center text-meta font-semibold md:min-h-0"
          >
            ← 回到考試成績
          </Link>
        )}
        <div className="min-w-0 flex-1">
          <GuideBreadcrumb crumbs={breadcrumb} />
        </div>
      </div>

      {notice && (
        <div
          className="alert-warning mb-4"
          dangerouslySetInnerHTML={{ __html: notice }}
        />
      )}

      {relatedUnits.length > 0 && (
        <section className="surface mb-4 border-l-4 border-l-accent p-4" aria-label="實務補充">
          <div className="section-title mb-2">把這一章用在實務情境</div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {relatedUnits.map((unit) => (
              <Link key={unit.id} to={`/learn/${unit.id}`} className="btn-secondary no-underline">
                {unit.title}
              </Link>
            ))}
          </div>
        </section>
      )}

      <ReadingLayout
        toc={
          <>
            <ReadingToc
              entries={contentHeadings}
              activeId={activeHeadingId}
              onSelect={(entry) => scrollToContentBlock(entry.id, entry.anchor)}
            />
            <details
              className={contentHeadings.length > 0 ? 'mt-5 border-t border-border pt-4' : ''}
              open={contentHeadings.length === 0}
            >
              <summary className="section-title cursor-pointer">PDF 目錄</summary>
              <div className="mt-3">
                <GuideOutlineTree
                  subjectId={subjectId ?? outlineGuide.subjectId}
                  rootIds={outlineGuide.root}
                  nodesById={outlineGuide.nodesById}
                  activeId={chapter.id}
                />
              </div>
            </details>
          </>
        }
      >
          <div ref={stickyProgressRef} className="sticky -top-4 md:-top-6 z-10 mb-3 bg-app-bg/90 px-0 py-1 backdrop-blur-sm">
            <ReadingProgressBar progress={readingProgress} />
          </div>
          {contentError && (
            <StatePanel tone="error" title="無法載入學習指引內容" className="mb-4">
              {contentError}
            </StatePanel>
          )}

          {!content && !contentError && (
            <StatePanel tone="loading" className="mb-4">
              載入學習指引內容中...
            </StatePanel>
          )}

          {sourcePages.length > 0 && (
            <ReadingAuxiliary title={`PDF 原頁截圖（${sourcePages.length} 頁）`} className="mb-4">
              <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4 mt-4">
                {sourcePages.map((page) => (
                  <figure key={page.index} className="border border-border rounded-lg overflow-hidden bg-white">
                    <img
                      src={publicAsset(page.image)}
                      alt={`PDF page ${page.label || page.page}`}
                      loading="lazy"
                      className="block w-full h-auto"
                    />
                    <figcaption className="px-3 py-2 text-meta text-text-light border-t border-border">
                      PDF {page.label || `第 ${page.page} 頁`}
                    </figcaption>
                  </figure>
                ))}
              </div>
            </ReadingAuxiliary>
          )}

          {hasChildChapters ? (
            <ReadingSurface>
              <div className="text-primary font-semibold mb-2">請選擇下層章節</div>
              <p className="text-body leading-7 text-text-light mb-4">
                這一層是 PDF 的章節容器，內容已依下層章節拆開，避免把多個章節連在同一頁閱讀。
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {childChapters.map((child) => (
                  <Link
                    key={child.id}
                    to={`/guide/${subjectId}/${child.id}`}
                    className="block surface-compact px-4 py-3 no-underline transition-colors hover:border-accent hover:bg-accent-soft"
                  >
                    <span className="block text-primary font-semibold">
                      {child.number ? `${child.number} ` : ''}{child.title}
                    </span>
                    <span className="block text-meta text-text-light mt-1">
                      PDF 第 {child.pageRange[0]}–{child.pageRange[1]} 頁
                    </span>
                  </Link>
                ))}
              </div>
            </ReadingSurface>
          ) : (
            <ReadingSurface>
              <ReadingContent>
                {hasBlocks ? (
                  <GuideBlocksRenderer
                    blocks={contentBlocks}
                    images={chapterImages}
                    examAnnotations={examAnnotationsByBlock}
                    showExamNotes={showExamNotes}
                  />
                ) : isMarkdown ? (
                  <div className="guide-content prose max-w-none text-reading text-app-text content-justify">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeRaw, rehypeKatex]}
                      components={{
                        h2: ({ children }) => (
                          <h2 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-lg font-bold text-primary mt-6 mb-2 border-b border-border pb-1">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-base font-semibold text-accent mt-4 mb-1">{children}</h3>
                        ),
                        h4: ({ children }) => (
                          <h4 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-reading font-semibold text-primary mt-4 mb-1">{children}</h4>
                        ),
                        h5: ({ children }) => (
                          <h5 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-reading font-semibold text-app-text mt-3 mb-1">{children}</h5>
                        ),
                        h6: ({ children }) => (
                          <h6 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-body font-semibold text-text-light mt-3 mb-1">{children}</h6>
                        ),
                        p: ({ children }) => (
                          <p className="mb-4 leading-[1.8] content-justify">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-outside pl-5 mb-3 space-y-1">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-outside pl-5 mb-3 space-y-1">{children}</ol>
                        ),
                        li: ({ children }) => (
                          <li className="leading-[1.8] content-justify">{children}</li>
                        ),
                        table: ({ children }) => (
                          <div className={`my-4 ${READING_WIDE_BOX_CLASS}`}>
                            <table className="table-soft text-ui">{children}</table>
                          </div>
                        ),
                        th: ({ children }) => (
                          <th className="whitespace-pre-line">{children}</th>
                        ),
                        td: ({ children }) => (
                          <td className="leading-6 whitespace-pre-line">{children}</td>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-app-text">{children}</strong>
                        ),
                      }}
                    >
                      {normalizedBody}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="guide-content prose max-w-none text-reading leading-[1.8] text-app-text space-y-4 content-justify">
                    {paragraphs.map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                )}
              </ReadingContent>
            </ReadingSurface>
          )}
          {colabNotebook && <ColabSection notebook={colabNotebook} />}
          {(prevChapter || nextChapter) && (
            <nav className="mt-4 mb-6 hidden grid-cols-2 gap-3 lg:grid" aria-label="上一章與下一章">
              {prevChapter ? (
                <Link
                  to={`/guide/${subjectId}/${prevChapter.id}`}
                  className="surface-compact p-4 no-underline hover:border-accent hover:bg-accent-soft"
                >
                  <span className="block text-meta font-semibold text-text-light">上一章</span>
                  <span className="mt-1 block font-semibold text-primary">{prevChapter.title}</span>
                </Link>
              ) : <span />}
              {nextChapter ? (
                <Link
                  to={`/guide/${subjectId}/${nextChapter.id}`}
                  className="surface-compact p-4 text-right no-underline hover:border-accent hover:bg-accent-soft"
                >
                  <span className="block text-meta font-semibold text-text-light">下一章</span>
                  <span className="mt-1 block font-semibold text-primary">{nextChapter.title}</span>
                </Link>
              ) : <span />}
            </nav>
          )}
      </ReadingLayout>
    </div>
    </div>

      <BackToTopButton
        show={showBackToTop}
        onClick={scrollToTop}
        className="bottom-[calc(5.75rem+var(--app-safe-bottom))] right-4 lg:bottom-8 lg:right-[19rem] xl:right-[21rem]"
      />

      {/* ── Mobile bottom chapter navigation bar ──────────────────────── */}
      <MobileActionBar className="lg:hidden">
        <div className="flex h-14 w-full items-stretch">
          {/* Prev chapter */}
          {prevChapter ? (
            <Link
              to={`/guide/${subjectId}/${prevChapter.id}`}
              className="touch-target flex items-center justify-center w-12 shrink-0 text-primary hover:bg-gray-50 active:bg-gray-100 border-r border-border"
              title={prevChapter.title}
              aria-label="上一章"
            >
              <span className="text-2xl leading-none">‹</span>
            </Link>
          ) : (
            <span className="flex items-center justify-center w-12 shrink-0 text-text-light/40 border-r border-border" aria-hidden="true">
              <span className="text-2xl leading-none">‹</span>
            </span>
          )}

          {/* Center: chapter info + opens drawer */}
          <button
            ref={drawerTriggerRef}
            type="button"
            className="touch-target flex-1 flex items-center justify-between gap-2 px-3 min-w-0 hover:bg-gray-50 active:bg-gray-100 text-left"
            onClick={() => setShowDrawer(true)}
            aria-label="開啟章節目錄"
            aria-expanded={showDrawer}
            aria-controls="guide-mobile-chapter-drawer"
          >
            <div className="flex flex-col items-start min-w-0">
              <span className="text-caption text-text-light leading-tight truncate max-w-full">{outlineGuide.subject}</span>
              <span className="text-ui font-semibold text-primary truncate max-w-full leading-snug">{chapter.title}</span>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-caption tabular-nums text-text-light bg-unanswered-soft border border-border px-1.5 py-0.5 rounded-full whitespace-nowrap">
                {currentFlatIndex + 1}/{flatIds.length}
              </span>
              <span className="text-text-light text-base leading-none" aria-hidden="true">☰</span>
            </div>
          </button>

          {/* Next chapter */}
          {nextChapter ? (
            <Link
              to={`/guide/${subjectId}/${nextChapter.id}`}
              className="touch-target flex items-center justify-center w-12 shrink-0 text-primary hover:bg-gray-50 active:bg-gray-100 border-l border-border"
              title={nextChapter.title}
              aria-label="下一章"
            >
              <span className="text-2xl leading-none">›</span>
            </Link>
          ) : (
            <span className="flex items-center justify-center w-12 shrink-0 text-text-light/40 border-l border-border" aria-hidden="true">
              <span className="text-2xl leading-none">›</span>
            </span>
          )}
        </div>
      </MobileActionBar>

      {/* ── Mobile chapter drawer ──────────────────────────────────────── */}
      <MobileChapterDrawer
        id="guide-mobile-chapter-drawer"
        open={showDrawer}
        title="章節目錄"
        onClose={() => setShowDrawer(false)}
        restoreFocusRef={drawerTriggerRef}
      >
        {chapterExamQuestionCount > 0 && (
          <div className="mb-4 border-b border-border pb-4">
            <ExamNotesSwitch checked={showExamNotes} onToggle={toggleExamNotes} className="flex w-full justify-between" />
          </div>
        )}
        <GuideOutlineTree
          subjectId={subjectId ?? outlineGuide.subjectId}
          rootIds={outlineGuide.root}
          nodesById={outlineGuide.nodesById}
          activeId={chapter.id}
          onNavigate={() => setShowDrawer(false)}
        />
        {contentHeadings.length > 0 && (
          <div className="mt-5 border-t border-border pt-4">
            <ReadingToc
              entries={contentHeadings}
              activeId={activeHeadingId}
              compact
              onSelect={(entry) => {
                setShowDrawer(false)
                requestAnimationFrame(() => scrollToContentBlock(entry.id, entry.anchor))
              }}
            />
          </div>
        )}
      </MobileChapterDrawer>
    </>
  )
}
