import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { articleMeta, articleNeighbors, articlePaths, loadLearningArticle, learningArticleIndex } from '../data/articleLoaders'
import type { GuideBlock, GuideFormula, LearningArticle } from '../types'
import { useScrollProgress, ReadingProgressBar, BackToTopButton } from '../components/shared/ReadingProgress'

function articleHeadingDomId(blockId: string) {
  return `article-heading-${blockId}`
}

function articleIndentStyle(depth: number) {
  const level = Math.max(depth - 2, 0)
  return {
    '--guide-indent-desktop': `${Math.min(level, 6) * 0.75}rem`,
    '--guide-indent-tablet': `${Math.min(level, 4) * 0.5}rem`,
    '--guide-indent-mobile': `${Math.min(level, 2) * 0.35}rem`,
  } as React.CSSProperties
}

function blockTextClass(block: GuideBlock) {
  if (block.type === 'heading') {
    if (block.depth <= 2) return 'text-lg font-bold text-primary border-b border-border pb-1 mt-7 mb-3'
    if (block.depth === 3) return 'text-base font-semibold text-accent mt-6 mb-2'
    if (block.depth === 4) return 'text-[0.96rem] font-semibold text-primary mt-4 mb-1.5'
    return 'text-[0.9rem] font-semibold text-app-text mt-3 mb-1'
  }
  if (block.type === 'question') return 'text-[0.9rem] font-semibold text-primary bg-[#f7fbff] border-l-4 border-accent px-3 py-2 rounded-r-lg my-3'
  if (block.type === 'answer') return 'text-[0.86rem] text-app-text bg-[#f8fafc] border border-border px-3 py-2 rounded-lg my-2'
  return 'text-[0.92rem] leading-8 text-app-text mb-3 content-justify'
}

function listMarkerClass(marker?: string) {
  if (!marker) return ''
  if (/^[A-Za-z]\.$/.test(marker)) return 'min-w-[1.8rem] text-primary font-semibold'
  if (marker === '•') return 'min-w-[1.05rem] text-accent font-semibold'
  return 'min-w-[1.05rem] text-text-light font-semibold'
}

function ArticleHtmlTable({ rows, html }: { rows?: string[][]; html?: string }) {
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

function ArticleFormulas({ formulas }: { formulas: GuideFormula[] }) {
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

function ArticleBlockBody({ block }: { block: GuideBlock }) {
  const formulas = blockFormulaEntries(block)
  if (formulas.length === 0) return <>{block.text}</>
  if (block.formulaOnly) return <ArticleFormulas formulas={formulas} />
  return (
    <>
      {block.text && <span>{block.text}</span>}
      <ArticleFormulas formulas={formulas} />
    </>
  )
}

function ArticleBlocks({ blocks }: { blocks: GuideBlock[] }) {
  return (
    <div className="guide-blocks text-app-text">
      {blocks.map((block) => {
        if (block.type === 'spacer') {
          return <div key={block.id} className="h-3" />
        }

        if (block.type === 'table' && (block.html || block.rows?.length)) {
          return (
            <div key={block.id} style={articleIndentStyle(block.depth)}>
              <ArticleHtmlTable rows={block.rows} html={block.html} />
            </div>
          )
        }

        if (block.type === 'heading') {
          const Tag = (block.depth <= 2 ? 'h2' : block.depth === 3 ? 'h3' : block.depth === 4 ? 'h4' : 'h5') as keyof React.JSX.IntrinsicElements
          return (
            <Tag
              key={block.id}
              id={articleHeadingDomId(block.id)}
              data-article-block-id={block.id}
              className={`guide-depth-block scroll-mt-20 ${blockTextClass(block)}`}
              style={articleIndentStyle(block.depth)}
            >
              {block.title}
            </Tag>
          )
        }

        if (block.type === 'list_item') {
          if (!block.marker) {
            return (
              <p
                key={block.id}
                className="guide-depth-block text-[0.92rem] leading-8 text-app-text mb-2 content-justify"
                style={articleIndentStyle(block.depth)}
              >
                <ArticleBlockBody block={block} />
              </p>
            )
          }
          return (
            <div
              key={block.id}
              className="guide-depth-block grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-[0.92rem] leading-8 text-app-text mb-2 content-justify"
              style={articleIndentStyle(block.depth)}
            >
              <span className={listMarkerClass(block.marker)}>{block.marker}</span>
              <div>
                <ArticleBlockBody block={block} />
              </div>
            </div>
          )
        }

        const hasFormulas = blockFormulaEntries(block).length > 0
        const style = {
          ...articleIndentStyle(block.depth),
          textIndent: !hasFormulas && block.type === 'paragraph' && block.indentFirstLine ? '2em' : undefined,
        }
        const Element = hasFormulas ? 'div' : 'p'
        return (
          <Element
            key={block.id}
            className={`guide-depth-block ${blockTextClass(block)}`}
            style={style}
          >
            <ArticleBlockBody block={block} />
          </Element>
        )
      })}
    </div>
  )
}

function scrollToSection(id: string) {
  const target = document.getElementById(articleHeadingDomId(id))
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function articleRoute(article: { route: string }, pathId?: string) {
  if (!pathId) return article.route
  return `${article.route}?path=${encodeURIComponent(pathId)}`
}

export default function LearningArticlePage() {
  const { articleId } = useParams<{ articleId: string }>()
  const [searchParams] = useSearchParams()
  const meta = articleMeta(articleId)
  const [article, setArticle] = useState<LearningArticle | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const pageRef = useRef<HTMLDivElement | null>(null)
  const { progress: readingProgress, showBackToTop, scrollToTop } = useScrollProgress(
    () => pageRef.current?.closest('main') ?? window,
  )

  useEffect(() => {
    pageRef.current?.closest('main')?.scrollTo({ top: 0 })
    window.scrollTo(0, 0)
  }, [articleId])

  useEffect(() => {
    let active = true
    setArticle(undefined)
    setLoadError(null)
    if (!articleId) return

    setLoading(true)
    loadLearningArticle(articleId)
      .then((loadedArticle) => {
        if (active) setArticle(loadedArticle)
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : String(error))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [articleId])

  const availablePaths = articlePaths(articleId)
  const selectedPath = availablePaths.find((path) => path.id === searchParams.get('path'))
  const selectedPathPosition = selectedPath && articleId ? selectedPath.articleIds.indexOf(articleId) + 1 : 0
  const neighbors = useMemo(
    () => articleId ? articleNeighbors(articleId, selectedPath?.id) : { previous: undefined, next: undefined },
    [articleId, selectedPath?.id],
  )

  if (!meta) {
    return <div className="page-shell text-error p-4">找不到主題文章：{articleId}</div>
  }

  if (loading) {
    return <div className="page-shell text-text-light p-4">文章載入中...</div>
  }

  if (loadError) {
    return <div className="page-shell text-error p-4">文章載入失敗：{loadError}</div>
  }

  if (!article) {
    return <div className="page-shell text-error p-4">找不到文章內容：{articleId}</div>
  }

  const level = learningArticleIndex.levels[article.levelId]
  const sourceRange = article.source.sourcePageRange
    ? `PDF 第 ${article.source.sourcePageRange[0]}–${article.source.sourcePageRange[1]} 頁`
    : '來源頁碼已對齊'

  return (
    <div className="page-shell" ref={pageRef}>
      <div className="sticky top-0 z-10 mb-3 bg-app-bg/90 py-1 backdrop-blur-sm">
        <ReadingProgressBar progress={readingProgress} />
      </div>
      <BackToTopButton show={showBackToTop} onClick={scrollToTop} className="bottom-8 right-4 md:right-8" />
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Learning article</div>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Link to="/articles" className="text-[0.82rem] font-semibold text-accent no-underline hover:underline">
                主題式文章
              </Link>
              <span className="text-[0.75rem] text-text-light">/</span>
              <Link to={`/articles?level=${article.levelId}`} className="text-[0.82rem] font-semibold text-accent no-underline hover:underline">
                {level.label}
              </Link>
              <span className="text-[0.75rem] text-text-light">/</span>
              <Link to={`/articles?level=${article.levelId}&subject=${article.subjectId}`} className="text-[0.82rem] font-semibold text-accent no-underline hover:underline">
                {article.subjectShortTitle}
              </Link>
              {selectedPath && (
                <>
                  <span className="text-[0.75rem] text-text-light">/</span>
                  <Link to={`/articles?path=${selectedPath.id}`} className="text-[0.82rem] font-semibold text-accent no-underline hover:underline">
                    {selectedPath.title}
                  </Link>
                </>
              )}
            </div>
            <h1 className="text-2xl font-bold leading-tight text-primary mb-2">{article.title}</h1>
            <p className="max-w-4xl text-[0.9rem] leading-7 text-text-light">
              {article.excerpt}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <span className="pill">{article.readingMinutes} 分鐘</span>
            <span className="pill pill-muted">{article.wordCount.toLocaleString()} 字</span>
            <span className="pill pill-muted">{sourceRange}</span>
            {selectedPath && (
              <span className="pill">路徑 {selectedPathPosition}/{selectedPath.articleCount}</span>
            )}
          </div>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <article className="surface p-5 sm:p-6">
          <div className="mb-5 rounded-lg border border-[#dbeafe] bg-[#f8fbff] p-4">
            <div className="section-title mb-3">本篇重點</div>
            <div className="flex flex-wrap gap-2">
              {article.subtopics.map((subtopic) => (
                <span key={subtopic} className="pill">
                  {subtopic}
                </span>
              ))}
            </div>
            {selectedPath && (
              <div className="mt-4 rounded-md border border-[#cfe0f5] bg-white px-3 py-2 text-[0.82rem] leading-6 text-text-light">
                目前位於「<span className="font-semibold text-primary">{selectedPath.title}</span>」第 {selectedPathPosition} / {selectedPath.articleCount} 篇。
              </div>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to={article.guideRoute} className="btn-outline">
                對照學習指引
              </Link>
              <Link to={article.practiceRoute} className="btn-muted">
                章節練習
              </Link>
            </div>
          </div>
          <ArticleBlocks blocks={article.blocks} />
        </article>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="surface p-4">
            <div className="section-title mb-3">文章目錄</div>
            {article.sections.length > 0 ? (
              <div className="space-y-1">
                {article.sections.slice(0, 24).map((section) => (
                  <button
                    key={section.id}
                    type="button"
                    className="block w-full rounded-md px-2 py-1.5 text-left text-[0.8rem] leading-5 text-text-light hover:bg-[#f8fbff] hover:text-accent"
                    style={{ paddingLeft: `${Math.max(section.depth - 2, 0) * 0.65 + 0.5}rem` }}
                    onClick={() => scrollToSection(section.id)}
                  >
                    {section.title}
                  </button>
                ))}
                {article.sections.length > 24 && (
                  <div className="px-2 pt-1 text-[0.75rem] text-text-light">
                    另有 {article.sections.length - 24} 個小節
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[0.82rem] leading-6 text-text-light">本篇以段落方式整理。</div>
            )}
          </div>
          {availablePaths.length > 0 && (
            <div className="surface p-4 mt-4">
              <div className="section-title mb-3">所屬學習路徑</div>
              <div className="space-y-2">
                {availablePaths.map((path) => (
                  <Link
                    key={path.id}
                    to={articleRoute(article, path.id)}
                    className={`block rounded-md border px-3 py-2 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff] ${
                      selectedPath?.id === path.id ? 'border-accent bg-[#f8fbff]' : 'border-border bg-white'
                    }`}
                  >
                    <div className="text-[0.82rem] font-semibold text-primary">{path.title}</div>
                    <div className="mt-1 text-[0.75rem] leading-5 text-text-light">
                      {path.articleCount} 篇 / 約 {path.estimatedMinutes} 分鐘
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {neighbors.previous ? (
          <Link to={articleRoute(neighbors.previous, selectedPath?.id)} className="surface-compact p-4 no-underline hover:border-accent hover:bg-[#f8fbff]">
            <div className="text-[0.75rem] font-semibold text-text-light">{selectedPath ? '路徑上一篇' : '上一篇'}</div>
            <div className="mt-1 font-semibold text-primary">{neighbors.previous.title}</div>
          </Link>
        ) : (
          <div className="surface-compact p-4 text-[0.85rem] text-text-light">{selectedPath ? '已是本路徑第一篇' : '已是第一篇文章'}</div>
        )}
        {neighbors.next ? (
          <Link to={articleRoute(neighbors.next, selectedPath?.id)} className="surface-compact p-4 text-right no-underline hover:border-accent hover:bg-[#f8fbff]">
            <div className="text-[0.75rem] font-semibold text-text-light">{selectedPath ? '路徑下一篇' : '下一篇'}</div>
            <div className="mt-1 font-semibold text-primary">{neighbors.next.title}</div>
          </Link>
        ) : (
          <div className="surface-compact p-4 text-right text-[0.85rem] text-text-light">{selectedPath ? '已是本路徑最後一篇' : '已是最後一篇文章'}</div>
        )}
      </div>
    </div>
  )
}
