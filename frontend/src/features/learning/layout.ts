/**
 * 學習頁（實務補充／實務專題／實作練習／主題診斷／精選例題對照）共用的版面 class。
 * 只在 features/learning 內使用；全站共用版面仍以 index.css 與 components/ui 為準。
 */

/** 整頁閱讀欄：標題與內容同寬，約 46rem（每行約 40 個中文字）。 */
export const READING_PAGE = 'page-shell w-full max-w-[46rem]'

/** 寬版頁面（卡片格、表格）中，單段說明文字的最大寬度。 */
export const READING_MEASURE = 'max-w-[46rem]'

/** 一排行動按鈕：手機直向堆疊（按鈕滿寬），sm 以上橫排換行。 */
export const ACTION_ROW = 'flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center'

/** 一排文字連結：手機直向堆疊，sm 以上橫排。 */
export const LINK_ROW = 'flex flex-col items-start sm:flex-row sm:flex-wrap sm:gap-x-5'

export function formatMinutes(minutes: number) {
  if (minutes < 60) return `約 ${minutes} 分鐘`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `約 ${hours} 小時 ${rest} 分鐘` : `約 ${hours} 小時`
}
