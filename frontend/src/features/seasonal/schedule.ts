/**
 * 節慶主題的純函式（無 import、無 DOM），由 tests/frontend_checks/seasonal_schedule_check.cjs
 * 直接轉譯後單元測試。主題登錄表在 themes.ts，React 狀態在 SeasonalProvider.tsx。
 */

/** 月／日（月份 1–12）。每年重複，不含年份。 */
export interface MonthDay {
  month: number
  day: number
}

/** 起訖都含在內；start 晚於 end 代表跨年（例如 12/20 → 1/5）。 */
export interface SeasonalWindow {
  id: string
  start: MonthDay
  end: MonthDay
}

/** 網址 `?seasonal=` 覆寫：'off' 強制關閉、主題 id 強制開啟；沒帶或看不懂就是 null（照日期）。 */
export type SeasonalOverride = { kind: 'off' } | { kind: 'force'; id: string } | null

const TAIPEI_OFFSET_MS = 8 * 60 * 60 * 1000

function ordinal(md: MonthDay): number {
  return md.month * 100 + md.day
}

/**
 * 台北時間（Asia/Taipei）的月／日。台灣自 1979 年後不實施夏令時間，固定 UTC+8，
 * 所以直接位移計算，不依賴執行環境的 Intl 時區資料。
 */
export function taipeiMonthDay(date: Date): MonthDay {
  const shifted = new Date(date.getTime() + TAIPEI_OFFSET_MS)
  return { month: shifted.getUTCMonth() + 1, day: shifted.getUTCDate() }
}

/** md 是否落在 [start, end]（含首尾）；start > end 時視為跨年區間。 */
export function isWithinWindow(md: MonthDay, window: Pick<SeasonalWindow, 'start' | 'end'>): boolean {
  const value = ordinal(md)
  const start = ordinal(window.start)
  const end = ordinal(window.end)
  if (start <= end) return value >= start && value <= end
  return value >= start || value <= end
}

/** 解析 `location.search`（hash 之前的 query），只認得 knownIds 與 'off'。 */
export function parseSeasonalOverride(search: string, knownIds: readonly string[]): SeasonalOverride {
  let raw: string | null = null
  try {
    raw = new URLSearchParams(search).get('seasonal')
  } catch {
    return null
  }
  if (raw === null) return null
  const value = raw.trim().toLowerCase()
  if (value === 'off' || value === 'none' || value === '0') return { kind: 'off' }
  if (knownIds.includes(value)) return { kind: 'force', id: value }
  return null
}

/**
 * 決定目前「可用」的主題：覆寫優先，其次依台北日期取登錄表中第一個符合的區間。
 * 使用者自己的開關不在這裡處理（主題仍可用，只是裝飾被關掉，頁尾開關要能再打開）。
 */
export function resolveSeasonalTheme<T extends SeasonalWindow>(
  themes: readonly T[],
  now: Date,
  override: SeasonalOverride,
): T | null {
  if (override?.kind === 'off') return null
  if (override?.kind === 'force') return themes.find((theme) => theme.id === override.id) ?? null
  const today = taipeiMonthDay(now)
  return themes.find((theme) => isWithinWindow(today, theme)) ?? null
}
