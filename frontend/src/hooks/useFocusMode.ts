import { useEffect, useSyncExternalStore } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * 專注模式（考試／計時作答用）。
 *
 * 頁面呼叫 `useFocusMode(active)`；active 為 true 時，AppShell 會：
 *   - 視窗 < 768px：隱藏整條站台 Header（含選單按鈕），並把 `--app-header-h` 設為 0，
 *     main 從畫面頂端開始，頁面自己的計時列可以用 `sticky top-0` 貼齊頂端；
 *     同時關閉並隱藏手機抽屜選單。
 *   - 視窗 >= 768px：收合左側 Sidebar，Header 保留。
 *
 * 還原規則：
 *   - 呼叫的元件 unmount、或 active 變回 false → 立即還原。
 *   - 每筆登記都綁定登記當下的 pathname；路由一換（即使元件沒 unmount）就不再生效，
 *     新路徑若仍要專注模式，hook 會以新 pathname 重新登記。
 *   - 多個元件同時登記時，任一個符合目前路徑就生效（以登記數計，不會互相蓋掉）。
 */

interface FocusEntry {
  pathname: string
}

let entries: readonly FocusEntry[] = []
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getSnapshot() {
  return entries
}

/** 頁面用：在作答進行中傳 true，結束（交卷、結果頁）傳 false。 */
export function useFocusMode(active: boolean) {
  const { pathname } = useLocation()

  useEffect(() => {
    if (!active) return
    const entry: FocusEntry = { pathname }
    entries = [...entries, entry]
    emit()
    return () => {
      entries = entries.filter((item) => item !== entry)
      emit()
    }
  }, [active, pathname])
}

/** 版面用（AppShell）：目前路徑是否處於專注模式。頁面通常不需要讀它。 */
export function useFocusModeActive(): boolean {
  const { pathname } = useLocation()
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  return current.some((entry) => entry.pathname === pathname)
}
