import type { GuideSearchIndexData, GuideSearchNode } from '../types'

/**
 * 搜尋索引（204 KB）只在使用者真的開啟搜尋或完整目錄頁時才載入，
 * 不進首頁 bundle。載入後留在模組層快取，同一個 session 不重複下載。
 */
let cache: GuideSearchIndexData | null = null
let pending: Promise<GuideSearchIndexData> | null = null

export function loadGuideSearchIndex(): Promise<GuideSearchIndexData> {
  if (cache) return Promise.resolve(cache)
  if (!pending) {
    pending = import('../generated/guideSearchIndex.json').then((mod) => {
      cache = mod.default as unknown as GuideSearchIndexData
      return cache
    })
  }
  return pending
}

/**
 * 比對前兩邊都要 NFKC 正規化。學習指引的標題大量使用全形括號，
 * 而且有 CJK 相容字（「數」可能是 U+F969），只正規化一邊會整批比不中。
 */
export function normalizeForSearch(text: string) {
  return text.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
}

export interface GuideSearchHit {
  node: GuideSearchNode
  subjectId: string
  subject?: string
  level: string
  /** 由外而內的祖先標題，供結果列顯示位置 */
  path: string[]
  /** 可跳轉的目標；OCR 補回的標題沒有對應區塊時為 undefined */
  to?: string
  score: number
}

const KIND_WEIGHT: Record<GuideSearchNode['k'], number> = { s: 0, c: 1, h: 2 }

export function searchGuides(index: GuideSearchIndexData, rawQuery: string, limit = 40): GuideSearchHit[] {
  const query = normalizeForSearch(rawQuery)
  if (query.length < 1) return []

  const hits: GuideSearchHit[] = []

  for (const [subjectId, guide] of Object.entries(index.guides)) {
    const byId = new Map(guide.nodes.map((node) => [node.id, node]))

    /** 沿父鏈往上找最近的 route——標題節點自己沒有 route。 */
    const routeFor = (node: GuideSearchNode): string | undefined => {
      let current: GuideSearchNode | undefined = node
      while (current) {
        if (current.r) return current.r
        current = current.p ? byId.get(current.p) : undefined
      }
      return undefined
    }

    const pathFor = (node: GuideSearchNode): string[] => {
      const titles: string[] = []
      let current = node.p ? byId.get(node.p) : undefined
      while (current && titles.length < 8) {
        titles.unshift(current.t)
        current = current.p ? byId.get(current.p) : undefined
      }
      return titles
    }

    for (const node of guide.nodes) {
      const position = normalizeForSearch(node.t).indexOf(query)
      if (position < 0) continue

      const base = routeFor(node)
      // x=1 是 OCR 補回、頁面上沒有對應區塊的標題，跳過去只會停在章節頁頂端，
      // 所以不給連結（渲染端據此顯示為不可點）。
      const to = node.x || !base
        ? undefined
        : node.k === 'h' && node.a
        ? `${base}#${node.a}`
        : base

      hits.push({
        node,
        subjectId,
        subject: guide.subject,
        level: guide.level,
        path: pathFor(node),
        to,
        score: KIND_WEIGHT[node.k] * 1000 + position * 10 + Math.min(node.t.length, 99) / 100,
      })
    }
  }

  hits.sort((a, b) => a.score - b.score)
  return hits.slice(0, limit)
}
