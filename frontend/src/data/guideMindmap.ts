import type { GuideMindmapData, GuideMindmapIndex } from '../types'

/**
 * 心智圖資料按科目分檔（每份 1–4 KB），開啟該科目時才載入；
 * 索引本身也是動態載入，不進首頁 bundle。
 */
const cache = new Map<string, GuideMindmapData>()
const pending = new Map<string, Promise<GuideMindmapData>>()
let indexCache: GuideMindmapIndex | null = null
let indexPending: Promise<GuideMindmapIndex> | null = null

export function loadMindmapIndex(): Promise<GuideMindmapIndex> {
  if (indexCache) return Promise.resolve(indexCache)
  if (!indexPending) {
    indexPending = import('../generated/guideMindmap/index.json').then((mod) => {
      indexCache = mod.default as unknown as GuideMindmapIndex
      return indexCache
    })
  }
  return indexPending
}

export function loadMindmap(subjectId: string): Promise<GuideMindmapData> {
  const hit = cache.get(subjectId)
  if (hit) return Promise.resolve(hit)
  let promise = pending.get(subjectId)
  if (!promise) {
    promise = import(`../generated/guideMindmap/${subjectId}.json`).then((mod) => {
      const data = mod.default as unknown as GuideMindmapData
      cache.set(subjectId, data)
      return data
    })
    pending.set(subjectId, promise)
  }
  return promise
}
