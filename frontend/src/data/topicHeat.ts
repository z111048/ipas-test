import type { GuideMindmapData, TopicHeatData } from '../types'

/**
 * 概念熱度資料（約 116 KB）。只有 /mindmap 切到概念軸時才載入，不進首頁 bundle。
 */
let cache: TopicHeatData | null = null
let pending: Promise<TopicHeatData> | null = null

export function loadTopicHeat(): Promise<TopicHeatData> {
  if (cache) return Promise.resolve(cache)
  if (!pending) {
    pending = import('../generated/topicHeat.json').then((mod) => {
      cache = mod.default as unknown as TopicHeatData
      return cache
    })
  }
  return pending
}

export interface ChapterRef {
  title: string
  /** 可能為 null：該層還沒有路由 */
  route: string | null
  subject: string
  level: string
}

/**
 * `guideKey:nodeId` → 章節標題與路由。
 * 章節定義只有 guideMindmap 一份（衍生自 toc_manifest），這裡只做查表、不複製。
 */
export function buildChapterIndex(maps: GuideMindmapData[]): Map<string, ChapterRef> {
  const index = new Map<string, ChapterRef>()
  for (const map of maps) {
    for (const node of map.nodes) {
      index.set(`${map.guideKey}:${node.i}`, {
        title: node.t,
        route: node.r,
        subject: map.subject,
        level: map.level,
      })
    }
  }
  return index
}
