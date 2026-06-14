import { Link, useSearchParams } from 'react-router-dom'
import { articleList, articlesForPath, learningArticleIndex, learningPath, learningPathList } from '../data/articleLoaders'
import type { LearningArticleLevelId, LearningArticleMeta, LearningPath } from '../types'

const LEVEL_ORDER: LearningArticleLevelId[] = ['junior', 'middle']

function levelLabel(levelId: LearningArticleLevelId) {
  return learningArticleIndex.levels[levelId].label
}

function pageLink({
  levelId,
  subjectId,
  pathId,
}: {
  levelId?: string
  subjectId?: string
  pathId?: string
}) {
  const params = new URLSearchParams()
  if (pathId) params.set('path', pathId)
  if (levelId) params.set('level', levelId)
  if (subjectId) params.set('subject', subjectId)
  const query = params.toString()
  return query ? `/articles?${query}` : '/articles'
}

function isLevelId(value: string | null): value is LearningArticleLevelId {
  return value === 'junior' || value === 'middle'
}

function articleRoute(article: LearningArticleMeta, pathId?: string) {
  if (!pathId) return article.route
  return `${article.route}?path=${encodeURIComponent(pathId)}`
}

function PathCard({ path, selected }: { path: LearningPath; selected: boolean }) {
  const levels = path.levelIds.map((levelId) => learningArticleIndex.levels[levelId].label).join(' / ')
  const firstArticle = learningArticleIndex.articlesById[path.startingArticleId]

  return (
    <Link
      to={pageLink({ pathId: path.id })}
      className={`group surface p-4 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff] ${
        selected ? 'border-accent bg-[#f8fbff]' : ''
      }`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="pill">{levels}</span>
        <span className="pill pill-muted">{path.articleCount} 篇</span>
        <span className="pill pill-muted">{path.estimatedMinutes} 分鐘</span>
      </div>
      <h2 className="text-[1rem] font-bold leading-snug text-primary group-hover:text-accent">
        {path.title}
      </h2>
      <p className="mt-2 text-[0.84rem] leading-6 text-text-light">
        {path.description}
      </p>
      {firstArticle && (
        <div className="mt-3 text-[0.76rem] font-semibold text-accent">
          從「{firstArticle.title}」開始
        </div>
      )}
    </Link>
  )
}

function ArticleCard({ article, activePathId }: { article: LearningArticleMeta; activePathId?: string }) {
  const sourceRange = article.source.sourcePageRange
    ? `PDF 第 ${article.source.sourcePageRange[0]}–${article.source.sourcePageRange[1]} 頁`
    : '來源頁碼已對齊'

  return (
    <Link to={articleRoute(article, activePathId)} className="group surface p-4 no-underline transition-colors hover:border-accent hover:bg-[#f8fbff]">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="pill">{article.levelLabel}</span>
            <span className="pill pill-muted">{article.subjectShortTitle}</span>
            <span className="text-[0.75rem] font-semibold text-text-light">
              {article.order.toString().padStart(2, '0')}
            </span>
          </div>
          <h2 className="text-[1.05rem] font-bold leading-snug text-primary group-hover:text-accent">
            {article.title}
          </h2>
          <p className="mt-2 line-clamp-2 text-[0.86rem] leading-6 text-text-light">
            {article.excerpt}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 md:justify-end">
          <span className="pill pill-muted">{article.readingMinutes} 分鐘</span>
          <span className="pill pill-muted">{article.sectionCount} 節</span>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {article.subtopics.slice(0, 4).map((subtopic) => (
          <span key={subtopic} className="rounded-md border border-border bg-white px-2 py-1 text-[0.72rem] font-semibold leading-5 text-text-light">
            {subtopic}
          </span>
        ))}
      </div>
      <div className="mt-3 text-[0.75rem] text-text-light">{sourceRange}</div>
    </Link>
  )
}

export default function LearningArticlesPage() {
  const [searchParams] = useSearchParams()
  const selectedLevel = isLevelId(searchParams.get('level')) ? searchParams.get('level') as LearningArticleLevelId : undefined
  const selectedSubject = searchParams.get('subject') ?? undefined
  const selectedPath = learningPath(searchParams.get('path') ?? undefined)
  const selectedPathId = selectedPath?.id

  const baseArticles = selectedPath ? articlesForPath(selectedPath.id) : articleList()
  const articles = baseArticles.filter((article) => {
    if (selectedLevel && article.levelId !== selectedLevel) return false
    if (selectedSubject && article.subjectId !== selectedSubject) return false
    return true
  })

  const visibleSubjects = LEVEL_ORDER
    .filter((levelId) => !selectedLevel || selectedLevel === levelId)
    .flatMap((levelId) => learningArticleIndex.levels[levelId].subjects.map((subject) => ({
      ...subject,
      levelId,
      levelLabel: levelLabel(levelId),
    })))

  return (
    <div className="page-shell">
      <div className="page-header mb-5">
        <div className="eyebrow mb-2">Learning articles</div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary mb-1">主題式文章</h1>
            <p className="max-w-4xl text-[0.9rem] leading-7 text-text-light">
              將初級與中級學習指引整理為可獨立閱讀的主題文章，並以跨章學習路徑串起基礎、資料、模型、生成式 AI、落地與治理。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="pill">{learningArticleIndex.articleCount} 篇文章</span>
            <span className="pill pill-muted">{learningArticleIndex.pathCount} 條路徑</span>
          </div>
        </div>
      </div>

      <div className="mb-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="section-title">系統學習路徑</h2>
          {selectedPath && (
            <Link to="/articles" className="text-[0.8rem] font-semibold text-accent no-underline hover:underline">
              顯示全部文章
            </Link>
          )}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {learningPathList().map((path) => (
            <PathCard key={path.id} path={path} selected={selectedPathId === path.id} />
          ))}
        </div>
      </div>

      <div className="surface p-4 mb-5">
        <div className="section-title mb-3">篩選學習路徑</div>
        <div className="mb-3 flex flex-wrap gap-2">
          <Link
            to={pageLink({ subjectId: selectedSubject, pathId: selectedPathId })}
            className={`btn-outline ${!selectedLevel ? 'border-accent bg-accent text-white' : 'border-border text-text-light hover:border-accent hover:text-accent'}`}
          >
            全部級別
          </Link>
          {LEVEL_ORDER.map((levelId) => (
            <Link
              key={levelId}
              to={pageLink({ levelId, pathId: selectedPathId })}
              className={`btn-outline ${selectedLevel === levelId ? 'border-accent bg-accent text-white' : 'border-border text-text-light hover:border-accent hover:text-accent'}`}
            >
              {levelLabel(levelId)}
            </Link>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={pageLink({ levelId: selectedLevel, pathId: selectedPathId })}
            className={`btn-muted ${!selectedSubject ? 'border-accent text-accent' : ''}`}
          >
            全部科目
          </Link>
          {visibleSubjects.map((subject) => (
            <Link
              key={`${subject.levelId}:${subject.id}`}
              to={pageLink({ levelId: subject.levelId, subjectId: subject.id, pathId: selectedPathId })}
              className={`btn-muted ${selectedSubject === subject.id ? 'border-accent text-accent' : ''}`}
              title={subject.title}
            >
              {subject.levelLabel} {subject.shortTitle}
            </Link>
          ))}
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="section-title">{selectedPath ? selectedPath.title : '文章列表'}</h2>
        <span className="text-[0.8rem] text-text-light">顯示 {articles.length} 篇</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} activePathId={selectedPathId} />
        ))}
      </div>
    </div>
  )
}
