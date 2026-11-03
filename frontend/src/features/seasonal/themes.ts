import type { SeasonalTheme } from './types'
import { halloweenDecor } from './halloween'

/**
 * 節慶主題登錄表。日期以台北時間判斷，起訖含首尾、每年重複；start 晚於 end 代表跨年。
 * 依序比對，第一個符合的生效，所以區間重疊時排前面的優先。
 *
 * 之後加主題的方式：在 ./<id>/ 做好 decor，於此加一筆，並在 index.css 補 `.theme-<id>` 底下的樣式。
 *   { id: 'christmas', label: '聖誕節', start: { month: 12, day: 15 }, end: { month: 12, day: 26 }, ... }
 *   { id: 'lunar-new-year', ... }  // 農曆年每年日期不同，屆時改成逐年列出區間
 */
export const SEASONAL_THEMES: readonly SeasonalTheme[] = [
  {
    id: 'halloween',
    label: '萬聖節',
    start: { month: 10, day: 15 },
    end: { month: 11, day: 7 },
    className: 'theme-halloween',
    decor: halloweenDecor,
  },
]

export const SEASONAL_THEME_IDS = SEASONAL_THEMES.map((theme) => theme.id)

/**
 * 安靜路由：閱讀與作答區完全不放裝飾（連頁首小圖示也收起）。
 * 考試作答中另由專注模式（useFocusModeActive）判斷，不在這裡。
 */
const QUIET_PREFIXES = ['/guide/', '/articles/', '/learn/', '/labs/', '/simulations/']

export function isQuietPath(pathname: string): boolean {
  return QUIET_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}
