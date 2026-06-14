import { Link, useParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeRaw from 'rehype-raw'
import rehypeKatex from 'rehype-katex'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import guideImagesRaw from '../generated/guideImages.json'
import type { ColabNotebook, GuideBlock, GuideContent, GuideFormula, GuideImageAsset, GuideImagesData, GuideOutlineNode, GuideOutlinesData } from '../types'
import { GUIDE_NOTICES } from '../constants/guideNotices'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'
import ColabSection from '../components/guide/ColabSection'
import { publicAsset } from '../utils/assets'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
const guideImages = guideImagesRaw as unknown as GuideImagesData
const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')
const colabNotebookModules = import.meta.glob<{ default: ColabNotebook }>('../generated/colabNotebooks/*/*.json')

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
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="leading-6 whitespace-pre-line">
                  {cell}
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

function GuideBlocksRenderer({ blocks, images }: { blocks: GuideBlock[]; images: GuideImageAsset[] }) {
  const imagesByHeading = images.reduce<Record<string, GuideImageAsset[]>>((acc, image) => {
    if (!image.headingBlockId) return acc
    acc[image.headingBlockId] = [...(acc[image.headingBlockId] ?? []), image]
    return acc
  }, {})

  const unmatchedImages = images.filter((image) => !image.headingBlockId || !blocks.some((block) => block.id === image.headingBlockId))

  const renderWithImages = (block: GuideBlock, element: React.ReactNode) => {
    const blockImages = imagesByHeading[block.id] ?? []
    if (blockImages.length === 0) return element
    return (
      <div key={`${block.id}-with-images`}>
        {element}
        {blockImages.map((image) => (
          <GuideImageFigure key={image.id} image={image} depth={block.depth} />
        ))}
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
  const outlineGuide = subjectId ? guideOutlines.guides[subjectId] : undefined
  const chapter = chapterId && outlineGuide ? outlineGuide.nodesById[chapterId] : undefined
  const [content, setContent] = useState<GuideContent | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)
  const [colabNotebook, setColabNotebook] = useState<ColabNotebook | null>(null)
  const [showDrawer, setShowDrawer] = useState(false)
  const contentScrollRef = useRef<HTMLDivElement | null>(null)

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
      .catch(() => {/* silently ignore missing notebooks */})
    return () => { cancelled = true }
  }, [chapter, outlineGuide])

  const breadcrumb = useMemo(() => {
    if (!outlineGuide || !chapter) return []
    const nodes: GuideOutlineNode[] = []
    let current: GuideOutlineNode | undefined = chapter
    while (current) {
      nodes.unshift(current)
      current = current.parentId ? outlineGuide.nodesById[current.parentId] : undefined
    }
    return nodes
  }, [chapter, outlineGuide])

  if (!outlineGuide || !chapter) {
    return <div className="page-shell text-error p-4">找不到章節：{chapterId}</div>
  }

  const body = content?.content ?? ''
  const contentBlocks = content?.blocks ?? []
  const hasBlocks = contentBlocks.length > 0
  const guideImageKey = `${outlineGuide.sourceKey ?? outlineGuide.key}:${chapter.id}`
  const chapterImages = guideImages.byChapter[guideImageKey] ?? []
  const normalizedBody = normalizeOcrSoftBreaks(body)
  const isMarkdown = content?.contentFormat === 'markdown' || body.trimStart().startsWith('#') || body.trimStart().startsWith('##')
  const paragraphs = hasBlocks
    ? contentBlocks.filter((block) => block.type === 'paragraph').map((block) => block.text ?? '').filter(Boolean)
    : isMarkdown ? [] : normalizedBody.split(/\n{2,}/).filter((p) => p.trim())
  const notice = chapterId ? GUIDE_NOTICES[chapterId] : undefined
  const sourcePages = content?.sourcePages ?? []
  const contentHeadings = hasBlocks
    ? contentBlocks
      .filter((block) => block.type === 'heading' && block.depth >= 3 && block.depth <= 5 && block.id && block.title)
      .map((block) => ({ id: block.id, anchor: block.anchor, level: block.depth, title: block.title ?? '' }))
    : content?.headings
      ?.filter((heading) => heading.level >= 3 && heading.level <= 4)
      .map((heading) => ({ ...heading, anchor: undefined as string | undefined })) ?? []
  const childChapters = chapter.children.map((childId) => outlineGuide.nodesById[childId]).filter(Boolean)
  const hasChildChapters = childChapters.length > 0
  const pageRange = `PDF 第 ${chapter.pageRange[0]}–${chapter.pageRange[1]} 頁`

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
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    const containerTop = container.getBoundingClientRect().top
    const targetTop = target.getBoundingClientRect().top
    const nextTop = container.scrollTop + targetTop - containerTop - 8
    container.scrollTo({
      top: nextTop,
      behavior: 'smooth',
    })
    if (Math.abs(container.scrollTop - nextTop) > 2 && container.scrollHeight <= container.clientHeight) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="page-shell h-full min-h-0 flex flex-col overflow-hidden">
      <div className="page-header mb-2 sm:mb-4 shrink-0">
        <div className="eyebrow mb-2 hidden sm:block">Guide</div>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-primary mb-1">{chapter.title}</h1>
            <p className="hidden sm:block text-[0.9rem] text-text-light">{outlineGuide.subject} › 學習指引原文（{content ? `共 ${body.length.toLocaleString()} 字元` : '載入中'}）</p>
          </div>
          <div className="hidden sm:flex flex-wrap gap-2">
            <span className="pill">{pageRange}</span>
            <span className="pill pill-muted">{paragraphs.length} 段落</span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-[0.8rem] text-text-light mb-2 sm:mb-4 shrink-0">
        <Link to={`/subject/${subjectId}`} className="text-accent no-underline hover:underline">
          {outlineGuide.subject}
        </Link>
        {breadcrumb.map((node) => (
          <span key={node.id} className="flex items-center gap-2">
            <span>/</span>
            <Link
              to={`/guide/${subjectId}/${node.id}`}
              className={`no-underline hover:underline ${node.id === chapter.id ? 'text-primary font-semibold' : 'text-accent'}`}
            >
              {node.number ? `${node.number} ` : ''}{node.title}
            </Link>
          </span>
        ))}
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
                  {contentHeadings.map((heading) => (
                    <button
                      key={`${heading.id}-${heading.title}`}
                      type="button"
                      onClick={() => scrollToContentBlock(heading.id, heading.anchor)}
                      className="block w-full rounded-md px-2 py-1 text-left text-[0.78rem] leading-5 text-primary no-underline hover:bg-[#f8fbff] hover:text-accent"
                      style={{ paddingLeft: `${Math.max(0, heading.level - 3) * 0.85}rem` }}
                    >
                      {heading.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>

        <div ref={contentScrollRef} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pr-1 app-scroll-stable pb-14 xl:pb-0">
          {contentError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 mb-4 text-sm text-red-700">
              無法載入學習指引內容：{contentError}
            </div>
          )}

          {!content && !contentError && (
            <div className="surface p-5 mb-4 text-text-light">
              載入學習指引內容中...
            </div>
          )}

          {sourcePages.length > 0 && (
            <details className="surface p-5 mb-4">
              <summary className="cursor-pointer text-primary font-semibold">
                PDF 原頁截圖（{sourcePages.length} 頁）
              </summary>
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
            </details>
          )}

          {hasChildChapters ? (
            <div className="surface p-5">
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
            </div>
          ) : (
          <div className="surface p-4 sm:p-5">
            {hasBlocks ? (
              <GuideBlocksRenderer blocks={contentBlocks} images={chapterImages} />
            ) : isMarkdown ? (
              <div className="guide-content prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text content-justify">
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
              <div className="guide-content prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text space-y-4 content-justify">
                {paragraphs.map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
              </div>
            )}
          </div>
          )}
          {colabNotebook && <ColabSection notebook={colabNotebook} />}
        </div>
      </div>

      {/* ── Mobile bottom chapter navigation bar ──────────────────────── */}
      <div className="xl:hidden fixed bottom-0 left-0 right-0 z-30 bg-white border-t border-border shadow-[0_-2px_10px_rgba(0,0,0,0.07)]">
        <div className="flex items-stretch h-14">
          {/* Prev chapter */}
          {prevChapter ? (
            <Link
              to={`/guide/${subjectId}/${prevChapter.id}`}
              className="flex items-center justify-center w-12 shrink-0 text-primary hover:bg-gray-50 active:bg-gray-100 border-r border-border"
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
            type="button"
            className="flex-1 flex items-center justify-between gap-2 px-3 min-w-0 hover:bg-gray-50 active:bg-gray-100 text-left"
            onClick={() => setShowDrawer(true)}
            aria-label="開啟章節目錄"
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
              className="flex items-center justify-center w-12 shrink-0 text-primary hover:bg-gray-50 active:bg-gray-100 border-l border-border"
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
      </div>

      {/* ── Mobile chapter drawer ──────────────────────────────────────── */}
      {/* Backdrop */}
      <div
        className={`xl:hidden fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 ${showDrawer ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setShowDrawer(false)}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div
        className={`xl:hidden fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-2xl flex flex-col max-h-[78vh] transition-transform duration-300 ease-out ${showDrawer ? 'translate-y-0' : 'translate-y-full'}`}
        role="dialog"
        aria-modal="true"
        aria-label="章節目錄"
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-2.5 pb-1 shrink-0">
          <div className="w-10 h-1 rounded-full bg-gray-200" />
        </div>
        {/* Drawer header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
          <span className="font-semibold text-primary text-sm">章節目錄</span>
          <button
            type="button"
            onClick={() => setShowDrawer(false)}
            className="text-text-light hover:text-primary p-1 -mr-1 rounded"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>
        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-4 py-3 pb-8 overscroll-contain">
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
                {contentHeadings.map((heading) => (
                  <button
                    key={`${heading.id}-${heading.title}`}
                    type="button"
                    onClick={() => {
                      setShowDrawer(false)
                      requestAnimationFrame(() => scrollToContentBlock(heading.id, heading.anchor))
                    }}
                    className="block w-full rounded-md px-2 py-1.5 text-left text-[0.82rem] leading-5 text-primary hover:bg-[#f8fbff] hover:text-accent active:bg-[#f0f7ff]"
                    style={{ paddingLeft: `${0.5 + Math.max(0, heading.level - 3) * 0.85}rem` }}
                  >
                    {heading.title}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
