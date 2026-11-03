import type { ComponentType } from 'react'
import type { SeasonalWindow } from './schedule'

export interface SeasonalCompanionProps {
  /** 定位用（例如 'absolute right-1 top-1'）；父層要是 positioned。 */
  className?: string
}

export interface SeasonalPassBannerProps {
  onDismiss: () => void
}

/**
 * 主題的裝飾元件。每一項都可省略；省略的插槽在該主題就不顯示。
 * 元件只在「主題開啟、使用者沒關、且不在安靜路由」時才會被渲染。
 */
export interface SeasonalDecor {
  /** 首頁主視覺（.hero-panel）角落的剪影，絕對定位，父層已是 relative + overflow hidden。 */
  HeroDecor?: ComponentType
  /** 頁首站名旁的小圖示（inline）。 */
  HeaderMark?: ComponentType
  /** 藏在頁面角落、可以點的小角色（真正的 button）。 */
  Companion?: ComponentType<SeasonalCompanionProps>
  /** 公告試題及格時的祝賀橫幅（可關閉）。 */
  PassBanner?: ComponentType<SeasonalPassBannerProps>
  /** 首頁第一次往下捲動時的一次性特效；不渲染任何東西，只掛事件。 */
  ScrollFlyer?: ComponentType
  /**
   * 即時批改答對時，在該題選項附近冒出的短動畫（約 0.8 秒）。由 SeasonalProvider 的特效層
   * 放在 fixed 圖層裡、以元件左上角對齊錨點；prefers-reduced-motion 時不會渲染。
   */
  Celebration?: ComponentType
}

export interface SeasonalTheme extends SeasonalWindow {
  /** 給人看的名稱（目前只在程式註解與除錯用）。 */
  label: string
  /** 主題開啟時加在 <html> 上的 class；所有裝飾樣式都掛在它底下。 */
  className: string
  decor: SeasonalDecor
}
