/**
 * 學習指引「章節資料檔」的動態 import 表與預先載入。
 * 原本 GuidePage 要等程式下載、執行完才開始請求內文與圖片清單，慢速網路上形成串接瀑布；
 * 網址一確定是某一章就先呼叫同一個動態 import，讓資料與頁面程式同時下載，
 * GuidePage 之後再呼叫時拿到的是同一份（已在下載或已完成）的模組，不會重複請求。
 * 章節清單不在此硬編：只用 glob 的 key（檔名 = {chapterId}.json）比對。
 */
import type { GuideContent, GuideImageAsset } from '../types'
import type { ContextMapData } from '../components/guide/ContextMap'

export const guideContentModules = import.meta.glob<{ default: GuideContent }>('../generated/guideContent/*/*.json')
export const guideImageModules = import.meta.glob<{ default: GuideImageAsset[] }>('../generated/guideImagesByChapter/*/*.json')
// 「本章脈絡」：檔名 = {chapterId}.json；沒有脈絡圖的章節就沒有對應 key。
export const contextMapModules = import.meta.glob<{ default: ContextMapData }>('../generated/contextMaps/*.json')

/** 預先下載該章內文檔、圖片清單檔與脈絡圖；任何失敗都吞掉，之後 GuidePage 自己載入時照原邏輯顯示錯誤。 */
export function prefetchGuideChapter(chapterId: string): void {
  if (!/^[\w-]+$/.test(chapterId)) return
  const suffix = `/${chapterId}.json`
  for (const modules of [guideContentModules, guideImageModules, contextMapModules]) {
    for (const [key, load] of Object.entries(modules)) {
      if (key.endsWith(suffix)) load().catch(() => {})
    }
  }
}
