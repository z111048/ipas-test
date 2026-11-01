/**
 * 把頁面捲回頂端。
 *
 * 這個 app 真正的捲動容器是 App.tsx 的 `<main id="main-content">`（overflow-y-scroll），
 * 不是 document——單呼叫 `window.scrollTo(0, 0)` 沒有任何效果。
 * window 也一起歸零，涵蓋 print／窄版等 main 不捲動的版面。
 */
export const MAIN_SCROLL_CONTAINER_ID = 'main-content'

export function scrollMainToTop() {
  if (typeof document === 'undefined') return
  document.getElementById(MAIN_SCROLL_CONTAINER_ID)?.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
}
