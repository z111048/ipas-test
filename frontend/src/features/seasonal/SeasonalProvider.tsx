import { useCallback, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import { parseSeasonalOverride, resolveSeasonalTheme } from './schedule'
import { SEASONAL_THEMES, SEASONAL_THEME_IDS, isQuietPath } from './themes'
import { SeasonalContext, setCelebrateListener, type SeasonalState } from './context'
import { FxLayer } from './fx'
import type { SeasonalTheme } from './types'

/** 使用者關掉某個主題的裝飾時寫入 'off'；打開就移除。以主題 id 分開存，關掉萬聖節不影響下一個節慶。 */
export function seasonalPrefKey(themeId: string) {
  return `ipas:seasonal:${themeId}`
}

function readPrefOff(themeId: string): boolean {
  try {
    return window.localStorage.getItem(seasonalPrefKey(themeId)) === 'off'
  } catch {
    return false
  }
}

function writePref(themeId: string, enabled: boolean) {
  try {
    if (enabled) window.localStorage.removeItem(seasonalPrefKey(themeId))
    else window.localStorage.setItem(seasonalPrefKey(themeId), 'off')
  } catch {
    // 私密模式／停用網站資料：只影響這次瀏覽
  }
}

interface InitialState {
  theme: SeasonalTheme | null
  enabled: boolean
}

/**
 * 啟動時決定一次（不跟著時鐘跳）：
 *   ?seasonal=off        → 沒有主題（與平常完全相同，頁尾也不出現開關）
 *   ?seasonal=<主題 id>   → 不看日期強制開啟，也不看使用者先前的「關」（方便測試與截圖）
 *   沒帶                  → 依台北日期；使用者在頁尾關過就維持關閉
 */
function initialState(): InitialState {
  const override = parseSeasonalOverride(window.location.search, SEASONAL_THEME_IDS)
  const theme = resolveSeasonalTheme(SEASONAL_THEMES, new Date(), override)
  if (!theme) return { theme: null, enabled: false }
  const enabled = override?.kind === 'force' ? true : !readPrefOff(theme.id)
  return { theme, enabled }
}

interface Pop {
  key: number
  x: number
  y: number
}

const POP_MS = 850

export default function SeasonalProvider({
  pathname,
  focusMode,
  children,
}: {
  pathname: string
  focusMode: boolean
  children: ReactNode
}) {
  const [{ theme, enabled: initialEnabled }] = useState(initialState)
  const [enabled, setEnabledState] = useState(initialEnabled)
  const quiet = focusMode || isQuietPath(pathname)
  const decorate = Boolean(theme && enabled && !quiet)

  const setEnabled = useCallback(
    (next: boolean) => {
      if (!theme) return
      setEnabledState(next)
      writePref(theme.id, next)
    },
    [theme],
  )

  // 主題 class 掛在 <html>：所有裝飾樣式都寫在它底下；安靜路由另外加 seasonal-quiet。
  useLayoutEffect(() => {
    if (!theme || !enabled) return
    const root = document.documentElement
    root.classList.add(theme.className)
    return () => root.classList.remove(theme.className)
  }, [theme, enabled])

  useLayoutEffect(() => {
    if (!theme || !enabled || !quiet) return
    const root = document.documentElement
    root.classList.add('seasonal-quiet')
    return () => root.classList.remove('seasonal-quiet')
  }, [theme, enabled, quiet])

  const [pops, setPops] = useState<Pop[]>([])
  const Celebration = decorate ? theme?.decor.Celebration : undefined

  useEffect(() => {
    if (!Celebration) return
    let seq = 0
    const timers = new Set<number>()
    setCelebrateListener((x, y) => {
      const key = ++seq
      setPops((prev) => [...prev.slice(-3), { key, x, y }])
      const timer = window.setTimeout(() => {
        timers.delete(timer)
        setPops((prev) => prev.filter((pop) => pop.key !== key))
      }, POP_MS)
      timers.add(timer)
    })
    return () => {
      setCelebrateListener(null)
      timers.forEach((timer) => window.clearTimeout(timer))
      setPops([])
    }
  }, [Celebration])

  const value = useMemo<SeasonalState>(
    () => ({ theme, enabled, decorate, setEnabled }),
    [theme, enabled, decorate, setEnabled],
  )

  return (
    <SeasonalContext.Provider value={value}>
      {children}
      {Celebration && pops.length > 0 && (
        <FxLayer>
          {pops.map((pop) => (
            <div key={pop.key} className="seasonal-pop" style={{ left: pop.x, top: pop.y }}>
              <Celebration />
            </div>
          ))}
        </FxLayer>
      )}
    </SeasonalContext.Provider>
  )
}
