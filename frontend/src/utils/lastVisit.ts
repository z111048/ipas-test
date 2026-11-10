/**
 * 「繼續上次進度」：只記最後一次造訪的學習指引、練習、公告試題或文章頁。
 * 存取一律容錯（無痕模式會丟例外）；版本或型別不符的資料視為沒有紀錄。
 */
const KEY = 'ipas:last-visit'
const VERSION = 1
const TRACKED = /^\/(guide\/[^/]+\/[^/]+|practice\/[^/]+\/[^/]+(\/[^/]+)?|exam\/[^/]+|articles\/[^/]+)\/?$/

export interface LastVisit {
  v: typeof VERSION
  path: string
  at: number
}

export function recordLastVisit(pathname: string) {
  if (!TRACKED.test(pathname)) return
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ v: VERSION, path: pathname, at: Date.now() }))
  } catch {
    // 儲存不可用就略過
  }
}

export function readLastVisit(): LastVisit | null {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const { v, path, at } = parsed as Record<string, unknown>
    if (v !== VERSION || typeof path !== 'string' || typeof at !== 'number') return null
    return TRACKED.test(path) ? { v, path, at } : null
  } catch {
    return null
  }
}
