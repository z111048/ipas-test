import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { articleMeta, articleNeighbors, articlePaths, loadLearningArticle, learningArticleIndex } from '../data/articleLoaders'
import type { GuideBlock, GuideFormula, LearningArticle, LearningPath } from '../types'
import { useScrollProgress, ReadingProgressBar, BackToTopButton } from '../components/shared/ReadingProgress'
import { PageHeader, StatePanel } from '../components/ui'
import { NAV_LABELS } from '../constants/navLabels'
import {
  READING_LIST_ITEM_CLASS,
  READING_PARAGRAPH_CLASS,
  READING_WIDE_BOX_CLASS,
  ReadingContent,
  ReadingLayout,
  ReadingSurface,
  ReadingToc,
} from '../components/reading'
import type { ReadingTocEntry } from '../components/reading'
import { preferredScrollBehavior } from '../utils/motion'

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
    if (block.depth === 4) return 'text-reading font-semibold text-primary mt-4 mb-1.5'
    return 'text-reading font-semibold text-app-text mt-3 mb-1'
  }
  if (block.type === 'question') return 'text-reading font-semibold text-primary bg-answered-soft border-l-4 border-accent px-3 py-2 rounded-r-lg my-3'
  if (block.type === 'answer') return 'text-reading text-app-text bg-unanswered-soft border border-border px-3 py-2 rounded-lg my-2'
  return READING_PARAGRAPH_CLASS
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
                className={`guide-depth-block ${READING_LIST_ITEM_CLASS}`}
                style={articleIndentStyle(block.depth)}
              >
                <ArticleBlockBody block={block} />
              </p>
            )
          }
          return (
            <div
              key={block.id}
              className={`guide-depth-block grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 ${READING_LIST_ITEM_CLASS}`}
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
  target.scrollIntoView({ behavior: preferredScrollBehavior(), block: 'start' })
}

function normalizeForCompare(text: string) {
  return text.replace(/[\s　]+/g, '').replace(/(?:…|\.{3})+$/, '')
}

/**
 * 摘要（excerpt）多半就是第一段截斷加上「…」。若第一段正文以摘要開頭，
 * 標題區就不再重複顯示摘要。
 */
function excerptRepeatsFirstParagraph(article: LearningArticle) {
  const excerpt = normalizeForCompare(article.excerpt ?? '')
  if (!excerpt) return true
  const first = article.blocks.find((block) => (block.type === 'paragraph' || block.type === 'list_item') && block.text?.trim())
  if (!first?.text) return false
  const firstText = normalizeForCompare(first.text)
  return firstText.startsWith(excerpt) || excerpt.startsWith(firstText)
}

function articleTocEntries(article: LearningArticle): ReadingTocEntry[] {
  return article.sections.map((section) => ({ id: section.id, title: section.title, level: section.depth }))
}

function LearningPathLinks({
  article,
  paths,
  selectedPathId,
}: {
  article: LearningArticle
  paths: LearningPath[]
  selectedPathId?: string
}) {
  return (
    <>
      <div className="section-title mb-3">所屬學習路徑</div>
      <div className="space-y-2">
        {paths.map((path) => (
          <Link
            key={path.id}
            to={articleRoute(article, path.id)}
            className={`block rounded-md border px-3 py-2 no-underline transition-colors hover:border-accent hover:bg-accent-soft ${
              selectedPathId === path.id ? 'border-accent bg-answered-soft' : 'border-border bg-white'
            }`}
          >
            <div className="text-ui font-semibold text-primary">{path.title}</div>
            <div className="mt-1 text-meta leading-5 text-text-light">
              {path.articleCount} 篇 / 約 {path.estimatedMinutes} 分鐘
            </div>
          </Link>
        ))}
      </div>
    </>
  )
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
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null)
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

  // Scroll-spy：目錄標出目前讀到的小節（main 是捲動容器）
  useEffect(() => {
    setActiveSectionId(null)
    const page = pageRef.current
    if (!article || !page) return
    const root = page.closest('main')
    const headingEls = article.sections
      .map((section) => document.getElementById(articleHeadingDomId(section.id)))
      .filter((el): el is HTMLElement => Boolean(el))
    if (headingEls.length === 0 || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const topmost = visible.reduce((a, b) => (a.boundingClientRect.top < b.boundingClientRect.top ? a : b))
        const id = topmost.target.getAttribute('data-article-block-id')
        if (id) setActiveSectionId(id)
      },
      { root, rootMargin: '0px 0px -70% 0px', threshold: [0, 1] },
    )
    headingEls.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [article])

  const availablePaths = articlePaths(articleId)
  const selectedPath = availablePaths.find((path) => path.id === searchParams.get('path'))
  const selectedPathPosition = selectedPath && articleId ? selectedPath.articleIds.indexOf(articleId) + 1 : 0
  const neighbors = useMemo(
    () => articleId ? articleNeighbors(articleId, selectedPath?.id) : { previous: undefined, next: undefined },
    [articleId, selectedPath?.id],
  )

  if (!meta) {
    return (
      <div className="page-shell">
        <StatePanel tone="error" title="找不到主題文章">
          {articleId}
        </StatePanel>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="page-shell">
        <StatePanel tone="loading">
          文章載入中...
        </StatePanel>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="page-shell">
        <PageHeader
          variant="plain"
          title="文章載入失敗"
          description={loadError}
          actions={<Link to="/articles" className="btn-primary">回到{NAV_LABELS.articles.label}</Link>}
        />
      </div>
    )
  }

  if (!article) {
    return (
      <div className="page-shell">
        <PageHeader
          variant="plain"
          title="找不到文章內容"
          description="這篇文章不存在，或內容已經移動。"
          actions={<Link to="/articles" className="btn-primary">回到{NAV_LABELS.articles.label}</Link>}
        />
      </div>
    )
  }

  const level = learningArticleIndex.levels[article.levelId]
  const sourceRange = article.source.sourcePageRange
    ? `PDF 第 ${article.source.sourcePageRange[0]}–${article.source.sourcePageRange[1]} 頁`
    : null
  const tocEntries = articleTocEntries(article)
  const selectTocEntry = (entry: ReadingTocEntry) => {
    setActiveSectionId(entry.id)
    scrollToSection(entry.id)
  }

  return (
    <div className="page-shell" ref={pageRef}>
      <div className="sticky top-0 z-10 mb-3 bg-app-bg/90 py-1 backdrop-blur-sm">
        <ReadingProgressBar progress={readingProgress} />
      </div>
      <BackToTopButton show={showBackToTop} onClick={scrollToTop} className="bottom-8 right-4 md:right-8" />
      <PageHeader
        className="mb-5"
        title={article.title}
        description={
          <>
            <div className="mb-2 flex flex-wrap items-center gap-x-2">
              <Link to="/articles" className="text-link text-ui">
                {NAV_LABELS.articles.label}
              </Link>
              <span className="text-meta text-text-light" aria-hidden="true">/</span>
              <Link to={`/articles?level=${article.levelId}`} className="text-link text-ui">
                {level.label}
              </Link>
              <span className="text-meta text-text-light" aria-hidden="true">/</span>
              <Link to={`/articles?level=${article.levelId}&subject=${article.subjectId}`} className="text-link text-ui">
                {article.subjectShortTitle}
              </Link>
              {selectedPath && (
                <>
                  <span className="text-meta text-text-light" aria-hidden="true">/</span>
                  <Link to={`/articles?path=${selectedPath.id}`} className="text-link text-ui">
                    {selectedPath.title}
                  </Link>
                </>
              )}
            </div>
            {!excerptRepeatsFirstParagraph(article) && (
              <p>
                {article.excerpt}
              </p>
            )}
          </>
        }
        meta={
          <>
            <span className="pill">{article.readingMinutes} 分鐘</span>
            <span className="pill pill-muted">{article.wordCount.toLocaleString()} 字</span>
            {sourceRange && <span className="pill pill-muted">{sourceRange}</span>}
            {selectedPath && (
              <span className="pill">路徑 {selectedPathPosition}/{selectedPath.articleCount}</span>
            )}
          </>
        }
      />

      <ReadingLayout
        className="mb-5"
        toc={
          <>
            {tocEntries.length > 0 ? (
              <ReadingToc entries={tocEntries} activeId={activeSectionId} onSelect={selectTocEntry} />
            ) : (
              <div className="text-ui leading-6 text-text-light">本篇以段落方式整理。</div>
            )}
            {availablePaths.length > 0 && (
              <div className="mt-5 border-t border-border pt-4">
                <LearningPathLinks article={article} paths={availablePaths} selectedPathId={selectedPath?.id} />
              </div>
            )}
          </>
        }
      >
        {tocEntries.length > 0 && (
          <details className="surface mb-4 p-4 lg:hidden">
            <summary className="flex min-h-11 cursor-pointer items-center font-semibold text-primary">
              本頁目錄（{tocEntries.length} 節）
            </summary>
            <div className="mt-2">
              <ReadingToc title="本頁目錄" entries={tocEntries} activeId={activeSectionId} onSelect={selectTocEntry} compact />
            </div>
          </details>
        )}
        <ReadingSurface>
          <ReadingContent>
            <div className="mb-6 rounded-xl bg-accent-soft p-4">
              <div className="section-title mb-3">本篇重點</div>
              <div className="flex flex-wrap gap-2">
                {article.subtopics.map((subtopic) => (
                  <span key={subtopic} className="pill bg-white">
                    {subtopic}
                  </span>
                ))}
              </div>
              {selectedPath && (
                <div className="mt-4 rounded-md bg-white px-3 py-2 text-ui leading-6 text-text-light">
                  目前位於「<span className="font-semibold text-primary">{selectedPath.title}</span>」第 {selectedPathPosition} / {selectedPath.articleCount} 篇。
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to={article.guideRoute} className="btn-primary">
                  對照學習指引
                </Link>
                <Link to={article.practiceRoute} className="btn-secondary">
                  章節練習
                </Link>
              </div>
            </div>
            <ArticleBlocks blocks={article.blocks} />
          </ReadingContent>
        </ReadingSurface>
        {availablePaths.length > 0 && (
          <div className="surface mt-4 p-4 lg:hidden">
            <LearningPathLinks article={article} paths={availablePaths} selectedPathId={selectedPath?.id} />
          </div>
        )}
      </ReadingLayout>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {neighbors.previous ? (
          <Link to={articleRoute(neighbors.previous, selectedPath?.id)} className="surface-compact p-4 no-underline hover:border-accent hover:bg-accent-soft">
            <div className="text-meta font-semibold text-text-light">{selectedPath ? '路徑上一篇' : '上一篇'}</div>
            <div className="mt-1 font-semibold text-primary">{neighbors.previous.title}</div>
          </Link>
        ) : (
          <div className="surface-compact p-4 text-ui text-text-light">{selectedPath ? '已是本路徑第一篇' : '已是第一篇文章'}</div>
        )}
        {neighbors.next ? (
          <Link to={articleRoute(neighbors.next, selectedPath?.id)} className="surface-compact p-4 text-right no-underline hover:border-accent hover:bg-accent-soft">
            <div className="text-meta font-semibold text-text-light">{selectedPath ? '路徑下一篇' : '下一篇'}</div>
            <div className="mt-1 font-semibold text-primary">{neighbors.next.title}</div>
          </Link>
        ) : (
          <div className="surface-compact p-4 text-right text-ui text-text-light">{selectedPath ? '已是本路徑最後一篇' : '已是最後一篇文章'}</div>
        )}
      </div>
    </div>
  )
}
