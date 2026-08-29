import { Link, useLocation, useParams } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
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
import { guideBreadcrumb } from '../data/guideNav'
import ColabSection from '../components/guide/ColabSection'
import { publicAsset } from '../utils/assets'
import { preferredScrollBehavior } from '../utils/motion'
import { useScrollProgress, ReadingProgressBar, BackToTopButton } from '../components/shared/ReadingProgress'
import { MobileActionBar, PageHeader, StatePanel } from '../components/ui'
import { MobileChapterDrawer, ReadingAuxiliary, ReadingContent, ReadingSurface } from '../components/reading'

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
    if (block.depth === 4) return 'text-[0.96rem] font-semibold text-primary mt-4 mb-1'
    if (block.depth === 5) return 'text-[0.9rem] font-semibold text-app-text mt-3 mb-1'
    return 'text-[0.86rem] font-semibold text-text-light mt-3 mb-1'
  }
  if (block.type === 'question') return 'text-[0.9rem] font-semibold text-primary bg-[#f7fbff] border-l-4 border-accent px-3 py-2 rounded-r-lg my-3'
  if (block.type === 'answer') return 'text-[0.86rem] text-app-text bg-[#f8fafc] border border-border px-3 py-2 rounded-lg my-2'
  return 'text-[0.9rem] leading-8 text-app-text mb-3 content-justify'
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

type GuideHeadingNavEntry = { id: string; anchor?: string; level: number; title: string }

// 「本節階層」的單一項目。來自 guide_ocr 補回的標題在頁面上沒有對應區塊（id 為空），
// 捲不過去，所以渲染成不可點的分組標籤——它們仍然是真實的結構，用來分組下層項目。
function GuideHeadingNavItem({
  heading, active, compact, onSelect,
}: {
  heading: GuideHeadingNavEntry
  active: boolean
  compact?: boolean
  onSelect: (blockId: string, anchor?: string) => void
}) {
  const indent = `${0.5 + Math.max(0, heading.level - 3) * 0.85}rem`
  const size = compact ? 'px-2 py-1.5 text-[0.82rem]' : 'px-2 py-1 text-[0.78rem]'

  if (!heading.id) {
    return (
      <div
        className={`block w-full border-l-2 border-l-transparent text-left leading-5 text-text-light ${size}`}
        style={{ paddingLeft: indent }}
      >
        {heading.title}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(heading.id, heading.anchor)}
      aria-current={active ? 'true' : undefined}
      className={`block w-full rounded-md border-l-2 text-left leading-5 no-underline transition-colors ${size} ${
        active
          ? 'border-l-accent bg-[#f0f7ff] font-semibold text-accent'
          : 'border-l-transparent text-primary hover:bg-[#f8fbff] hover:text-accent'
      }`}
      style={{ paddingLeft: indent }}
    >
      {heading.title}
    </button>
  )
}

function GuideHtmlTable({ rows, html }: { rows?: string[][]; html?: string }) {
  if (html) {
    return (
      <div
        className="guide-depth-block overflow-x-auto my-4"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  }
  if (!rows?.length) return null
  const [header, ...bodyRows] = rows
  return (
    <div className="guide-depth-block overflow-x-auto my-4">
      <table className="table-soft text-sm table-auto">
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
    <div className="guide-formulas mt-2 space-y-1 overflow-x-auto text-[0.9rem]">
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
      <figcaption className="mt-2 text-[0.78rem] leading-5 text-text-light">
        {caption}
      </figcaption>
    </figure>
  )
}

function GuideExamReferenceNotes({ annotations, depth }: { annotations: GuideExamAnnotation[]; depth: number }) {
  if (annotations.length === 0) return null
  const visibleAnnotations = annotations.slice(0, 8)
  const hiddenCount = annotations.length - visibleAnnotations.length
  const examLabels = Array.from(new Set(annotations.map((annotation) => annotation.examLabel)))

  return (
    <details
      className="guide-depth-block my-3 rounded-md border border-[#f2d5a2] bg-[#fffaf1] px-3 py-2 text-[0.82rem] leading-6 text-app-text"
      style={blockIndentStyle(depth)}
    >
      <summary className="cursor-pointer text-primary">
        <span className="font-semibold">歷屆試題</span>
        <span className="ml-2 text-[0.76rem] text-text-light">
          {annotations.length} 題曾引用此段
          {examLabels.length > 0 ? ` · ${examLabels.slice(0, 2).join('、')}${examLabels.length > 2 ? ` 等 ${examLabels.length} 份` : ''}` : ''}
        </span>
      </summary>
      <div className="mt-2 space-y-2">
        {visibleAnnotations.map((annotation) => (
          <div key={annotation.id} className="border-t border-[#f3dfbd] pt-2 first:border-t-0 first:pt-0">
            <div className="flex flex-wrap items-center gap-2">
              <Link to={annotation.route} className="font-semibold text-accent no-underline hover:underline">
                {annotation.examLabel} 第 {annotation.questionNumber} 題
              </Link>
              <span className="rounded-full border border-[#f3dfbd] bg-white px-2 py-0.5 text-[0.72rem] font-semibold text-primary">
                答案 {annotation.answer}
              </span>
            </div>
            <div className="mt-1 text-[0.8rem] leading-6 text-app-text content-justify">
              {annotation.question}
            </div>
            {annotation.reasons?.[0] && (
              <div className="mt-1 text-[0.75rem] leading-5 text-text-light">
                {annotation.reasons[0]}
              </div>
            )}
          </div>
        ))}
        {hiddenCount > 0 && (
          <div className="border-t border-[#f3dfbd] pt-2 text-[0.76rem] text-text-light">
            另有 {hiddenCount} 題引用此區塊。
          </div>
        )}
      </div>
    </details>
  )
}

function GuideBlocksRenderer({
  blocks,
  images,
  examAnnotations,
}: {
  blocks: GuideBlock[]
  images: GuideImageAsset[]
  examAnnotations: Record<string, GuideExamAnnotation[]>
}) {
  const imagesByHeading = images.reduce<Record<string, GuideImageAsset[]>>((acc, image) => {
    if (!image.headingBlockId) return acc
    acc[image.headingBlockId] = [...(acc[image.headingBlockId] ?? []), image]
    return acc
  }, {})

  const unmatchedImages = images.filter((image) => !image.headingBlockId || !blocks.some((block) => block.id === image.headingBlockId))

  const renderWithImages = (block: GuideBlock, element: React.ReactNode) => {
    const blockImages = imagesByHeading[block.id] ?? []
    const blockAnnotations = examAnnotations[block.id] ?? []
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
                className="guide-depth-block text-[0.9rem] leading-7 text-app-text mb-2 content-justify"
                style={blockIndentStyle(block.depth)}
              >
                <GuideBlockBody block={block} />
              </Element>
            ))
          }
          return renderWithImages(block, (
            <div
              key={block.id}
              className="guide-depth-block grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-[0.9rem] leading-7 text-app-text mb-2 content-justify"
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
  const outlineGuide = subjectId ? guideOutlines.guides[subjectId] : undefined
  const chapter = chapterId && outlineGuide ? outlineGuide.nodesById[chapterId] : undefined
  const [content, setContent] = useState<GuideContent | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)
  const [examAnnotationsByBlock, setExamAnnotationsByBlock] = useState<Record<string, GuideExamAnnotation[]>>({})
  const [colabNotebook, setColabNotebook] = useState<ColabNotebook | null>(null)
  const [showDrawer, setShowDrawer] = useState(false)
  const contentScrollRef = useRef<HTMLDivElement | null>(null)
  const drawerTriggerRef = useRef<HTMLButtonElement | null>(null)
  const scrollToContentBlockRef = useRef<((id: string, anchor?: string) => void) | null>(null)
  const [activeHeadingId, setActiveHeadingId] = useState<string | null>(null)
  const { progress: readingProgress, showBackToTop, scrollToTop } = useScrollProgress(() => contentScrollRef.current)

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
    const deadline = performance.now() + 12000

    const stop = () => {
      cancelled = true
      window.clearTimeout(timer)
    }
    const tick = () => {
      if (cancelled) return
      const container = contentScrollRef.current
      const height = container?.scrollHeight ?? document.documentElement.scrollHeight
      if (height !== lastHeight) {
        lastHeight = height
        stable = 0
        scrollToContentBlockRef.current?.(anchor, anchor)
      } else {
        stable += 1
      }
      if (stable < 4 && performance.now() < deadline) {
        timer = window.setTimeout(tick, 250)
      }
    }
    const frame = requestAnimationFrame(tick)

    window.addEventListener('wheel', stop, { passive: true, once: true })
    window.addEventListener('touchstart', stop, { passive: true, once: true })
    window.addEventListener('keydown', stop, { once: true })
    return () => {
      cancelAnimationFrame(frame)
      stop()
      window.removeEventListener('wheel', stop)
      window.removeEventListener('touchstart', stop)
      window.removeEventListener('keydown', stop)
    }
  }, [location.hash, content])

  if (!outlineGuide || !chapter) {
    return (
      <div className="page-shell">
        <StatePanel tone="error" title="找不到章節">
          {chapterId}
        </StatePanel>
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
  const chapterExamBlockCount = chapterExamAnnotationSummary?.guideBlocks ?? Object.keys(examAnnotationsByBlock).length
  const normalizedBody = normalizeOcrSoftBreaks(body)
  const isMarkdown = content?.contentFormat === 'markdown' || body.trimStart().startsWith('#') || body.trimStart().startsWith('##')
  const paragraphs = hasBlocks
    ? contentBlocks.filter((block) => block.type === 'paragraph').map((block) => block.text ?? '').filter(Boolean)
    : isMarkdown ? [] : normalizedBody.split(/\n{2,}/).filter((p) => p.trim())
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
    const out: { id: string; anchor?: string; level: number; title: string }[] = []
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

  const contentHeadings = hierarchyHeadings.length > 0
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


  const scrollToContentBlock = (id: string, anchor?: string) => {
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
    if (!target) return
    if (!container) {
      target.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'start' })
      return
    }
    const containerTop = container.getBoundingClientRect().top
    const targetTop = target.getBoundingClientRect().top
    const nextTop = container.scrollTop + targetTop - containerTop - 8
    container.scrollTo({
      top: nextTop,
      behavior: preferredScrollBehavior(),
    })
    if (Math.abs(container.scrollTop - nextTop) > 2 && container.scrollHeight <= container.clientHeight) {
      target.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'start' })
    }
  }
  scrollToContentBlockRef.current = scrollToContentBlock

  return (
    <div className="page-shell h-full min-h-0 flex flex-col overflow-hidden">
      <PageHeader
        className="mb-2 shrink-0 sm:mb-4"
        eyebrow={<span className="hidden sm:inline">Guide</span>}
        title={chapter.title}
        description={
          <span className="hidden sm:inline">
            {outlineGuide.subject} › 學習指引原文（{content ? `共 ${body.length.toLocaleString()} 字元` : '載入中'}）
          </span>
        }
        meta={
          <div className="hidden flex-wrap gap-2 sm:flex">
            <span className="pill">{pageRange}</span>
            <span className="pill pill-muted">{paragraphs.length} 段落</span>
            {chapterExamQuestionCount > 0 && (
              <span className="pill">歷屆試題 {chapterExamQuestionCount} 題</span>
            )}
          </div>
        }
      />

      <div className="mb-2 sm:mb-4 shrink-0">
        <GuideBreadcrumb crumbs={breadcrumb} />
      </div>

      {notice && (
        <div
          className="alert-warning mb-4 shrink-0"
          dangerouslySetInnerHTML={{ __html: notice }}
        />
      )}

      <div className="hidden sm:block surface shrink-0 p-4 sm:p-5 mb-4">
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="pill">
            {paragraphs.length} 段落
          </span>
          <span className="pill">
            {body.length.toLocaleString()} 字元
          </span>
          <span className="pill">
            {pageRange}
          </span>
          {chapterExamQuestionCount > 0 && (
            <span className="pill">
              歷屆試題 {chapterExamQuestionCount} 題 / {chapterExamBlockCount} 處
            </span>
          )}
          {sourcePages.length > 0 && (
            <span className="pill">
              PDF {sourcePages[0].label || sourcePages[0].page}–{sourcePages[sourcePages.length - 1].label || sourcePages[sourcePages.length - 1].page}
            </span>
          )}
        </div>
        {hasChildChapters && (
          <>
            <div className="section-title mb-2 mt-4">下層章節</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {childChapters.map((child) => (
                <Link
                  key={child.id}
                  to={`/guide/${subjectId}/${child.id}`}
                  className="block surface-compact px-4 py-3 text-primary no-underline transition-colors hover:border-accent hover:bg-[#f8fbff]"
                >
                  <span className="block text-[0.9rem] font-semibold">
                    {child.number ? `${child.number} ` : ''}{child.title}
                  </span>
                  <span className="block text-[0.74rem] text-text-light mt-1">
                    PDF 第 {child.pageRange[0]}–{child.pageRange[1]} 頁
                  </span>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="flex flex-col xl:grid xl:grid-cols-[minmax(220px,280px)_1fr] xl:grid-rows-1 gap-4 flex-1 min-h-0 overflow-hidden">
        <aside className="hidden xl:flex xl:flex-col surface z-20 p-4 sm:p-5 xl:h-full xl:overflow-hidden">
          <div className="h-full overflow-y-auto overflow-x-hidden pr-1 scrollbar-hidden">
            <div className="section-title mb-3">PDF 目錄</div>
            <GuideOutlineTree
              subjectId={subjectId ?? outlineGuide.subjectId}
              rootIds={outlineGuide.root}
              nodesById={outlineGuide.nodesById}
              activeId={chapter.id}
            />
            {contentHeadings.length > 0 && (
              <div className="mt-5 border-t border-border pt-4">
                <div className="section-title mb-3">本節階層</div>
                <div className="space-y-1">
                  {contentHeadings.map((heading, index) => (
                    <GuideHeadingNavItem
                      key={`${heading.id || heading.anchor || index}-${heading.title}`}
                      heading={heading}
                      active={Boolean(heading.id) && activeHeadingId === heading.id}
                      onSelect={scrollToContentBlock}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>

        <div ref={contentScrollRef} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pr-1 app-scroll-stable pb-[calc(5rem+var(--app-safe-bottom))] xl:pb-0">
          <div className="sticky top-0 z-10 -mt-0 mb-3 bg-app-bg/90 px-0 py-1 backdrop-blur-sm">
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
                    <figcaption className="px-3 py-2 text-[0.78rem] text-text-light border-t border-border">
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
              <p className="text-[0.9rem] leading-7 text-text-light mb-4">
                這一層是 PDF 的章節容器，內容已依下層章節拆開，避免把多個章節連在同一頁閱讀。
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {childChapters.map((child) => (
                  <Link
                    key={child.id}
                    to={`/guide/${subjectId}/${child.id}`}
                    className="block surface-compact px-4 py-3 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff]"
                  >
                    <span className="block text-primary font-semibold">
                      {child.number ? `${child.number} ` : ''}{child.title}
                    </span>
                    <span className="block text-[0.78rem] text-text-light mt-1">
                      PDF 第 {child.pageRange[0]}–{child.pageRange[1]} 頁
                    </span>
                  </Link>
                ))}
              </div>
            </ReadingSurface>
          ) : (
            <ReadingSurface>
              <ReadingContent className="text-[0.9rem] leading-8 sm:text-[0.95rem]">
                {hasBlocks ? (
                  <GuideBlocksRenderer
                    blocks={contentBlocks}
                    images={chapterImages}
                    examAnnotations={examAnnotationsByBlock}
                  />
                ) : isMarkdown ? (
                  <div className="guide-content prose prose-sm max-w-none text-app-text content-justify">
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
                          <h4 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-[0.96rem] font-semibold text-primary mt-4 mb-1">{children}</h4>
                        ),
                        h5: ({ children }) => (
                          <h5 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-[0.9rem] font-semibold text-app-text mt-3 mb-1">{children}</h5>
                        ),
                        h6: ({ children }) => (
                          <h6 id={headingAnchor(plainText(children))} className="scroll-mt-4 text-[0.86rem] font-semibold text-text-light mt-3 mb-1">{children}</h6>
                        ),
                        p: ({ children }) => (
                          <p className="mb-3 leading-8 content-justify">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-outside pl-5 mb-3 space-y-1">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-outside pl-5 mb-3 space-y-1">{children}</ol>
                        ),
                        li: ({ children }) => (
                          <li className="leading-7 content-justify">{children}</li>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4">
                            <table className="table-soft text-sm">{children}</table>
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
                  <div className="guide-content prose prose-sm max-w-none text-app-text space-y-4 content-justify">
                    {paragraphs.map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                )}
              </ReadingContent>
            </ReadingSurface>
          )}
          {colabNotebook && <ColabSection notebook={colabNotebook} />}
        </div>
      </div>

      <BackToTopButton
        show={showBackToTop}
        onClick={scrollToTop}
        className="bottom-[calc(5.75rem+var(--app-safe-bottom))] right-4 xl:bottom-8 xl:right-8"
      />

      {/* ── Mobile bottom chapter navigation bar ──────────────────────── */}
      <MobileActionBar className="xl:hidden">
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
            <span className="flex items-center justify-center w-12 shrink-0 text-gray-300 border-r border-border">
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
              <span className="text-[0.64rem] text-text-light leading-none truncate max-w-full">{outlineGuide.subject}</span>
              <span className="text-[0.82rem] font-semibold text-primary truncate max-w-full leading-snug mt-0.5">{chapter.title}</span>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-[0.68rem] text-text-light bg-gray-100 px-1.5 py-0.5 rounded-full whitespace-nowrap">
                {currentFlatIndex + 1}/{flatIds.length}
              </span>
              <span className="text-text-light/60 text-base leading-none">☰</span>
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
            <span className="flex items-center justify-center w-12 shrink-0 text-gray-300 border-l border-border">
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
        <GuideOutlineTree
          subjectId={subjectId ?? outlineGuide.subjectId}
          rootIds={outlineGuide.root}
          nodesById={outlineGuide.nodesById}
          activeId={chapter.id}
          onNavigate={() => setShowDrawer(false)}
        />
        {contentHeadings.length > 0 && (
          <div className="mt-5 border-t border-border pt-4">
            <div className="section-title mb-3">本節階層</div>
            <div className="space-y-0.5">
              {contentHeadings.map((heading, index) => (
                <GuideHeadingNavItem
                  key={`${heading.id || heading.anchor || index}-${heading.title}`}
                  heading={heading}
                  active={Boolean(heading.id) && activeHeadingId === heading.id}
                  compact
                  onSelect={(blockId, anchor) => {
                    setShowDrawer(false)
                    requestAnimationFrame(() => scrollToContentBlock(blockId, anchor))
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </MobileChapterDrawer>
    </div>
  )
}
