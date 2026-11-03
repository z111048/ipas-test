import { createContext, useContext } from 'react'
import type { SeasonalTheme } from './types'
import { prefersReducedMotion } from './fx'

export interface SeasonalState {
  /** 目前可用的主題（日期內或被網址強制開啟）；null = 沒有節慶，畫面與平常完全相同。 */
  theme: SeasonalTheme | null
  /** 使用者是否開著裝飾（頁尾開關）。 */
  enabled: boolean
  /** 這一頁要不要畫裝飾：theme && enabled && 不在安靜路由（閱讀區、作答中）。 */
  decorate: boolean
  setEnabled: (enabled: boolean) => void
}

export const SeasonalContext = createContext<SeasonalState>({
  theme: null,
  enabled: false,
  decorate: false,
  setEnabled: () => {},
})

export function useSeasonal(): SeasonalState {
  return useContext(SeasonalContext)
}

/** 目前要畫裝飾的主題；不畫時回傳 null。 */
export function useSeasonalDecor(): SeasonalTheme | null {
  const { theme, decorate } = useSeasonal()
  return decorate ? theme : null
}

// ── 答對慶祝 ─────────────────────────────────────────────────────────────
// 從事件處理器（點選、鍵盤）直接呼叫，不經 React 狀態；SeasonalProvider 只在
// 要畫裝飾、且主題有 Celebration 時才登記 listener。

type CelebrateListener = (x: number, y: number) => void
let celebrateListener: CelebrateListener | null = null

export function setCelebrateListener(listener: CelebrateListener | null) {
  celebrateListener = listener
}

/** 即時批改答對時呼叫；anchor 是使用者選的選項（或該題卡片）。主題沒開時什麼都不做。 */
export function celebrateCorrectAnswer(anchor: Element | null | undefined) {
  if (!celebrateListener || !anchor || prefersReducedMotion()) return
  const rect = anchor.getBoundingClientRect()
  const size = 44
  const x = Math.min(Math.max(rect.right - size - 12, 4), window.innerWidth - size - 4)
  const y = Math.min(Math.max(rect.top - size / 2, 4), window.innerHeight - size - 4)
  celebrateListener(x, y)
}
