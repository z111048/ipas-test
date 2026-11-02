import type { GuideBlock } from '../types'

/**
 * 講義區塊要顯示的 PDF 頁（0-based index）。
 *
 * 跨頁合併的區塊（例如被接回的斷段），資料的 `pageIndex` 依簽章慣例取後頁，
 * 但讀者要找的是它**開始**的那一頁，所以顯示一律取 `sourcePageIndexes[0]`
 * （使用者 2026-11-02 決定）；沒有 sourcePageIndexes 才退回 `pageIndex`。
 * 錨點不受影響。前端任何「第 N 頁」標籤或連結都要經過這裡，不要直接讀 `pageIndex`
 * （tests/test_guide_rebuild_2026_11.py 有靜態檢查）。
 */
export function guideBlockDisplayPageIndex(
  block: Pick<GuideBlock, 'pageIndex' | 'sourcePageIndexes'>,
): number | undefined {
  const first = block.sourcePageIndexes?.[0]
  return typeof first === 'number' ? first : block.pageIndex
}
