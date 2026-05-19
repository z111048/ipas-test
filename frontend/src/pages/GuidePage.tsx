import { Link, useParams } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import type { GuideContent, GuideOutlineNode, GuideOutlinesData } from '../types'
import { GUIDE_NOTICES } from '../constants/guideNotices'
import GuideOutlineTree from '../components/guide/GuideOutlineTree'

const guideOutlines = guideOutlinesRaw as GuideOutlinesData
const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')
const assetBase = import.meta.env.BASE_URL.replace(/\/$/, '')

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

function publicAsset(path: string) {
  return `${assetBase}${path.startsWith('/') ? path : `/${path}`}`
}

export default function GuidePage() {
  const { subjectId, chapterId } = useParams<{ subjectId: string; chapterId: string }>()
  const outlineGuide = subjectId ? guideOutlines.guides[subjectId] : undefined
  const chapter = chapterId && outlineGuide ? outlineGuide.nodesById[chapterId] : undefined
  const [content, setContent] = useState<GuideContent | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)

  useEffect(() => {
    window.scrollTo(0, 0)
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
    return <div className="text-error p-4">找不到章節：{chapterId}</div>
  }

  const body = content?.content ?? ''
  const normalizedBody = normalizeOcrSoftBreaks(body)
  const isMarkdown = content?.contentFormat === 'markdown' || body.trimStart().startsWith('#') || body.trimStart().startsWith('##')
  const paragraphs = isMarkdown ? [] : normalizedBody.split(/\n{2,}/).filter((p) => p.trim())
  const notice = chapterId ? GUIDE_NOTICES[chapterId] : undefined
  const sourcePages = content?.sourcePages ?? []
  const childChapters = chapter.children.map((childId) => outlineGuide.nodesById[childId]).filter(Boolean)
  const hasChildChapters = childChapters.length > 0
  const pageRange = `PDF 第 ${chapter.pageRange[0]}–${chapter.pageRange[1]} 頁`

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">{chapter.title}</div>
      <div className="text-text-light mb-4">
        {outlineGuide.subject} › 學習指引原文（{content ? `共 ${body.length.toLocaleString()} 字元` : '載入中'}）
      </div>

      <div className="flex flex-wrap gap-2 text-[0.8rem] text-text-light mb-4">
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
          className="bg-[#fef9e7] border-l-4 border-warning rounded-lg p-4 mb-4 text-[0.88rem] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: notice }}
        />
      )}

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
            📄 {paragraphs.length} 段落
          </span>
          <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
            📝 {body.length.toLocaleString()} 字元
          </span>
          <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
            {pageRange}
          </span>
          {sourcePages.length > 0 && (
            <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
              PDF {sourcePages[0].label || sourcePages[0].page}–{sourcePages[sourcePages.length - 1].label || sourcePages[sourcePages.length - 1].page}
            </span>
          )}
        </div>
        {hasChildChapters && (
          <>
            <div className="text-[0.82rem] text-text-light font-semibold mb-2 mt-4">下層章節</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {childChapters.map((child) => (
                <Link
                  key={child.id}
                  to={`/guide/${subjectId}/${child.id}`}
                  className="block bg-[#f7fbff] text-primary px-4 py-3 rounded-lg border border-accent/20 no-underline hover:border-accent hover:bg-[#eef7ff]"
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

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(220px,280px)_1fr] gap-4">
        <aside className="bg-card rounded-xl shadow-sm border border-border p-5 h-fit xl:sticky xl:top-4">
          <div className="text-[0.82rem] text-text-light font-semibold mb-3">PDF 目錄</div>
          <GuideOutlineTree
            subjectId={subjectId ?? outlineGuide.subjectId}
            rootIds={outlineGuide.root}
            nodesById={outlineGuide.nodesById}
            activeId={chapter.id}
          />
        </aside>

        <div>
          {contentError && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-4 text-sm">
              無法載入學習指引內容：{contentError}
            </div>
          )}

          {!content && !contentError && (
            <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4 text-text-light">
              載入學習指引內容中...
            </div>
          )}

          {sourcePages.length > 0 && (
            <details className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
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
            <div className="bg-card rounded-xl shadow-sm border border-border p-5">
              <div className="text-primary font-semibold mb-2">請選擇下層章節</div>
              <p className="text-[0.9rem] leading-7 text-text-light mb-4">
                這一層是 PDF 的章節容器，內容已依下層章節拆開，避免把多個章節連在同一頁閱讀。
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {childChapters.map((child) => (
                  <Link
                    key={child.id}
                    to={`/guide/${subjectId}/${child.id}`}
                    className="block border border-border rounded-lg px-4 py-3 no-underline hover:border-accent hover:bg-[#f7fbff]"
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
          <div className="bg-card rounded-xl shadow-sm border border-border p-5">
            {isMarkdown ? (
              <div className="prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h2: ({ children }) => (
                    <h2 className="text-lg font-bold text-primary mt-6 mb-2 border-b border-border pb-1">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-semibold text-accent mt-4 mb-1">{children}</h3>
                  ),
                  h4: ({ children }) => (
                    <h4 className="text-[0.96rem] font-semibold text-primary mt-4 mb-1">{children}</h4>
                  ),
                  h5: ({ children }) => (
                    <h5 className="text-[0.9rem] font-semibold text-app-text mt-3 mb-1">{children}</h5>
                  ),
                  h6: ({ children }) => (
                    <h6 className="text-[0.86rem] font-semibold text-text-light mt-3 mb-1">{children}</h6>
                  ),
                  p: ({ children }) => (
                    <p className="mb-3 leading-8">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-outside pl-5 mb-3 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-outside pl-5 mb-3 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="leading-7">{children}</li>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-4">
                      <table className="border-collapse w-full text-sm">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-border bg-[#eef5ff] text-accent px-3 py-2 text-left font-semibold">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-border px-3 py-2 leading-6">{children}</td>
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
              <div className="prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text space-y-4">
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
