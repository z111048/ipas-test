import learningArticleIndexRaw from '../generated/learningArticles/index.json'
import type { LearningArticle, LearningArticleIndex, LearningArticleMeta } from '../types'

type JsonModule = { default: unknown }

export const learningArticleIndex = learningArticleIndexRaw as unknown as LearningArticleIndex

const articleModules = import.meta.glob<JsonModule>('../generated/learningArticles/*/*.json')

/**
 * 快取分兩層。原本只有一個 `Map<string, Promise<...>>`，會把**失敗的 promise 也永久留下**——
 * build-time import 幾乎不會 reject 所以看不出來，改成 runtime fetch 之後
 * 一次網路抖動就等於那篇文章在這個 session 裡永遠載不出來。
 */
const cache = new Map<string, LearningArticle | undefined>()
const pending = new Map<string, Promise<LearningArticle | undefined>>()

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

export function loadLearningArticle(articleId: string): Promise<LearningArticle | undefined> {
  // `has` 而非 `get`：查不到的文章會快取成 undefined，不該每次重試
  if (cache.has(articleId)) return Promise.resolve(cache.get(articleId))

  const inFlight = pending.get(articleId)
  if (inFlight) return inFlight

  const meta = articleMeta(articleId)
  if (!meta) return Promise.resolve(undefined)

  const moduleKey = `../generated/learningArticles/${meta.levelLabel}/${meta.source.contentRef}`
  const loader = articleModules[moduleKey]
  if (!loader) {
    cache.set(articleId, undefined)
    return Promise.resolve(undefined)
  }

  const promise = loader()
    .then((module) => {
      const article = module.default as LearningArticle
      cache.set(articleId, article)
      return article
    })
    .finally(() => {
      // 失敗不進 cache，只清 pending —— 下次呼叫可以重試
      pending.delete(articleId)
    })
  pending.set(articleId, promise)
  return promise
}
