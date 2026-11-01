import { useCallback, useSyncExternalStore } from 'react'

/** 與 Tailwind `lg` 斷點一致：以上放常駐側欄，以下改用底部面板／收合區塊。 */
export const WIDE_LAYOUT_QUERY = '(min-width: 1024px)'

function hasMatchMedia() {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
}

export function matchesMediaQuery(query: string) {
  return hasMatchMedia() ? window.matchMedia(query).matches : false
}

/** 訂閱 CSS media query；第一次 render 就拿到正確值，不會先閃一次窄版。 */
export function useMediaQuery(query: string) {
  const subscribe = useCallback((onChange: () => void) => {
    if (!hasMatchMedia()) return () => {}
    const list = window.matchMedia(query)
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [query])
  return useSyncExternalStore(subscribe, () => matchesMediaQuery(query), () => false)
}

/** 手機寬度（< 768px，Tailwind `md` 以下）。 */
export function isNarrowViewport() {
  return !matchesMediaQuery('(min-width: 768px)')
}
