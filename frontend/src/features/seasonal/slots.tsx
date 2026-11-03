import { useState } from 'react'
import { useSeasonal, useSeasonalDecor } from './context'
import type { SeasonalCompanionProps } from './types'

/**
 * 頁面放置裝飾的插槽。主題沒開、使用者關掉、或在安靜路由時一律回傳 null，
 * 所以頁面不用自己判斷，也保證「主題關閉時畫面與平常完全相同」。
 */

export function SeasonalHeroDecor() {
  const Decor = useSeasonalDecor()?.decor.HeroDecor
  return Decor ? <Decor /> : null
}

export function SeasonalHeaderMark() {
  const Mark = useSeasonalDecor()?.decor.HeaderMark
  return Mark ? <Mark /> : null
}

export function SeasonalCompanion(props: SeasonalCompanionProps) {
  const Companion = useSeasonalDecor()?.decor.Companion
  return Companion ? <Companion {...props} /> : null
}

export function SeasonalScrollFlyer() {
  const Flyer = useSeasonalDecor()?.decor.ScrollFlyer
  return Flyer ? <Flyer /> : null
}

/** 公告試題成績頁：pass 時顯示祝賀橫幅，使用者可關閉。 */
export function SeasonalPassBanner({ pass }: { pass: boolean }) {
  const Banner = useSeasonalDecor()?.decor.PassBanner
  const [dismissed, setDismissed] = useState(false)
  if (!Banner || !pass || dismissed) return null
  return <Banner onDismiss={() => setDismissed(true)} />
}

/** 頁尾開關「節慶裝飾：開／關」。只有節慶期間（或網址強制開啟）才出現。 */
export function SeasonalFooterToggle({ className = '' }: { className?: string }) {
  const { theme, enabled, setEnabled } = useSeasonal()
  if (!theme) return null
  return (
    <button
      type="button"
      className={`seasonal-toggle ${className}`}
      aria-pressed={enabled}
      onClick={() => setEnabled(!enabled)}
    >
      節慶裝飾：{enabled ? '開' : '關'}
    </button>
  )
}
