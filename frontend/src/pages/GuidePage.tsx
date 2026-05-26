import { Link, useParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import type { GuideBlock, GuideContent, GuideOutlineNode, GuideOutlinesData } from '../types'
import { GUIDE_NOTICES } from '../constants/guideNotices'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'
import { publicAsset } from '../utils/assets'

const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')

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

function GuideHtmlTable({ rows }: { rows: string[][] }) {
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

function GuideBlocksRenderer({ blocks }: { blocks: GuideBlock[] }) {
  return (
    <div className="guide-blocks text-app-text">
      {blocks.map((block) => {
        if (block.type === 'table' && block.rows?.length) {
          return (
            <div key={block.id} style={blockIndentStyle(block.depth)}>
              <GuideHtmlTable rows={block.rows} />
            </div>
          )
        }

        if (block.type === 'list_item') {
          if (!block.marker) {
            return (
              <p
                key={block.id}
                className="guide-depth-block text-[0.9rem] leading-7 text-app-text mb-2 content-justify"
                style={blockIndentStyle(block.depth)}
              >
                {block.text}
              </p>
            )
          }
          return (
            <div
              key={block.id}
              className="guide-depth-block grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-[0.9rem] leading-7 text-app-text mb-2 content-justify"
              style={blockIndentStyle(block.depth)}
            >
              <span className={listMarkerClass(block.marker)}>{block.marker}</span>
              <span className={listTextClass(block.marker)}>{block.text}</span>
            </div>
          )
        }

        if (block.type === 'heading') {
          const Tag = (block.depth <= 2 ? 'h2' : block.depth === 3 ? 'h3' : block.depth === 4 ? 'h4' : block.depth === 5 ? 'h5' : 'h6') as keyof React.JSX.IntrinsicElements
          return (
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
          )
        }

        return (
          <p
            key={block.id}
            className={`guide-depth-block ${blockTextClass(block)}`}
            style={{
              ...blockIndentStyle(block.depth),
              textIndent: block.type === 'paragraph' && block.indentFirstLine ? '2em' : undefined,
            }}
          >
            {block.text}
          </p>
        )
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
  const contentScrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (contentScrollRef.current) contentScrollRef.current.scrollTop = 0
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
      <div className="page-header mb-4 shrink-0">
        <div className="eyebrow mb-2">Guide</div>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary mb-1">{chapter.title}</h1>
            <p className="text-[0.9rem] text-text-light">{outlineGuide.subject} › 學習指引原文（{content ? `共 ${body.length.toLocaleString()} 字元` : '載入中'}）</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="pill">{pageRange}</span>
            <span className="pill pill-muted">{paragraphs.length} 段落</span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-[0.8rem] text-text-light mb-4 shrink-0">
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

      <div className="surface shrink-0 p-4 sm:p-5 mb-4">
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

      <div className="grid grid-cols-1 grid-rows-[auto_minmax(0,1fr)] xl:grid-cols-[minmax(220px,280px)_1fr] xl:grid-rows-1 gap-4 flex-1 min-h-0 overflow-hidden">
        <aside className="surface z-20 h-fit max-h-[30vh] overflow-hidden p-4 md:max-h-[28vh] sm:p-5 xl:h-full xl:max-h-none">
          <div className="h-full max-h-[calc(30vh-2rem)] md:max-h-[calc(28vh-2rem)] xl:max-h-full overflow-y-auto overflow-x-hidden pr-1 scrollbar-hidden">
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

        <div ref={contentScrollRef} className="min-h-0 overflow-y-auto overflow-x-hidden pr-1 app-scroll-stable">
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
              <GuideBlocksRenderer blocks={contentBlocks} />
            ) : isMarkdown ? (
              <div className="guide-content prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text content-justify">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
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
        </div>
      </div>
    </div>
  )
}
