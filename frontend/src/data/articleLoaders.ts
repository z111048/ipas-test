import learningArticleIndexRaw from '../generated/learningArticles/index.json'
import type { LearningArticle, LearningArticleIndex, LearningArticleMeta } from '../types'

type JsonModule = { default: unknown }

export const learningArticleIndex = learningArticleIndexRaw as unknown as LearningArticleIndex

const articleModules = import.meta.glob<JsonModule>('../generated/learningArticles/*/*.json')
const cache = new Map<string, Promise<LearningArticle | undefined>>()

export function articleMeta(articleId?: string): LearningArticleMeta | undefined {
  if (!articleId) return undefined
  return learningArticleIndex.articlesById[articleId]
}

export function articleList() {
  return learningArticleIndex.flatArticleIds
    .map((id) => learningArticleIndex.articlesById[id])
    .filter(Boolean)
}

export function learningPath(pathId?: string) {
  if (!pathId) return undefined
  return learningArticleIndex.pathsById[pathId]
}

export function learningPathList() {
  return learningArticleIndex.learningPaths
}

export function articlesForPath(pathId?: string) {
  const path = learningPath(pathId)
  if (!path) return []
  return path.articleIds
    .map((id) => learningArticleIndex.articlesById[id])
    .filter(Boolean)
}

export function articlePaths(articleId?: string) {
  const meta = articleMeta(articleId)
  return meta?.pathIds
    .map((pathId) => learningArticleIndex.pathsById[pathId])
    .filter(Boolean) ?? []
}

export function articleNeighbors(articleId: string, pathId?: string) {
  const ids = learningPath(pathId)?.articleIds ?? learningArticleIndex.flatArticleIds
  const index = ids.indexOf(articleId)
  return {
    previous: index > 0 ? learningArticleIndex.articlesById[ids[index - 1]] : undefined,
    next: index >= 0 && index < ids.length - 1
      ? learningArticleIndex.articlesById[ids[index + 1]]
      : undefined,
  }
}

export function loadLearningArticle(articleId: string) {
  const cached = cache.get(articleId)
  if (cached) return cached

  const meta = articleMeta(articleId)
  if (!meta) return Promise.resolve(undefined)

  const moduleKey = `../generated/learningArticles/${meta.levelLabel}/${meta.source.contentRef}`
  const loader = articleModules[moduleKey]
  const promise = loader
    ? loader().then((module) => module.default as LearningArticle)
    : Promise.resolve(undefined)
  cache.set(articleId, promise)
  return promise
}
