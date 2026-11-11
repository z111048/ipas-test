/**
 * 路由頁面的動態 import 與「連結意圖預先載入」。
 * App.tsx 的 lazy() 與這裡的預先載入共用同一組 import 函式，確保是同一個 chunk。
 * 學習指引章節另外預先載入該章的內文檔與圖片清單，避免「先等頁面程式、再請求資料」的串接瀑布。
 *
 * 章節資料只在「使用者已經確定要看這一章」時才預先載入（網址本來就是該章，或已經點下連結），
 * 不在滑鼠移上／手指按下時做：Chromium 會記住失敗的動態 import，同一個檔在整頁重新載入前不會再請求，
 * 若在推測階段剛好斷線，之後真的點進去就會一直顯示載入失敗。
 */
import { prefetchGuideChapter } from './guideChapterModules'

export const importGuidePage = () => import('../pages/GuidePage')
export const importExamPage = () => import('../pages/ExamPage')
export const importPracticePage = () => import('../pages/PracticePage')

const PREFETCHERS: ReadonlyArray<readonly [string, () => Promise<unknown>]> = [
  ['#/guide/', importGuidePage],
  ['#/exam/', importExamPage],
  ['#/practice/', importPracticePage],
]

/** 從 href 或 hash 取出章節代號（#/guide/{subjectId}/{chapterId}，忽略 ? 之後）；不是章節網址回傳 null。 */
function guideChapterIdFromHref(href: string): string | null {
  return /^#\/guide\/[^/?#]+\/([^/?#]+)/.exec(href)?.[1] ?? null
}

// 首次載入：網址已是某一章，使用者本來就要看，不算推測性下載，所以不受省流量模式限制。
// 放在模組載入時執行（比 App 的 useEffect 早，與頁面程式的請求幾乎同時發出）。
const firstChapter = guideChapterIdFromHref(window.location.hash)
if (firstChapter) prefetchGuideChapter(firstChapter)

// 點下章節連結：和路由切換同一刻開始抓該章資料，頁面程式還在下載時資料也一起下載。
// 用 capture 階段，趕在路由處理點擊之前；同樣不算推測性下載，不受省流量模式限制。
document.addEventListener(
  'click',
  (event) => {
    if (!(event.target instanceof Element)) return
    const href = event.target.closest('a')?.getAttribute('href')
    const chapterId = href ? guideChapterIdFromHref(href) : null
    if (chapterId) prefetchGuideChapter(chapterId)
  },
  { capture: true, passive: true },
)

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
