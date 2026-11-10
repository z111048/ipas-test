/**
 * 路由頁面的動態 import 與「連結意圖預先載入」。
 * App.tsx 的 lazy() 與這裡的預先載入共用同一組 import 函式，確保是同一個 chunk。
 */
export const importGuidePage = () => import('../pages/GuidePage')
export const importExamPage = () => import('../pages/ExamPage')
export const importPracticePage = () => import('../pages/PracticePage')

const PREFETCHERS: ReadonlyArray<readonly [string, () => Promise<unknown>]> = [
  ['#/guide/', importGuidePage],
  ['#/exam/', importExamPage],
  ['#/practice/', importPracticePage],
]

/** 滑鼠移到或手指按下站內連結時先下載該頁 chunk；每類只觸發一次，省流量模式不做。回傳解除函式。 */
export function installRoutePrefetch(): () => void {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
  if (connection?.saveData) return () => {}
  const done = new Set<string>()
  const onIntent = (event: Event) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const href = target.closest('a')?.getAttribute('href')
    if (!href) return
    for (const [prefix, load] of PREFETCHERS) {
      if (!href.startsWith(prefix) || done.has(prefix)) continue
      done.add(prefix)
      load().catch(() => done.delete(prefix))
      return
    }
  }
  document.addEventListener('mouseover', onIntent, { passive: true })
  document.addEventListener('touchstart', onIntent, { passive: true })
  return () => {
    document.removeEventListener('mouseover', onIntent)
    document.removeEventListener('touchstart', onIntent)
  }
}
