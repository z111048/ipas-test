import guideNavRaw from '../generated/guideNav.json'
import { resourceLevels } from './resourceRegistry'
import type { GuideNavData, GuideNavNode } from '../types'

/**
 * 章/節兩層的導覽樹（13 KB），側欄與麵包屑共用。
 * 完整階層樹（含 1,143 個標題節點、449 KB）只有 GuidePage 的「本節階層」需要，
 * 搜尋與完整目錄頁則動態載入 guideSearchIndex.json。
 */
export const guideNav = guideNavRaw as unknown as GuideNavData

export interface BreadcrumbCrumb {
  label: string
  to?: string
}

/** 順 parentId 往上走，取得 [章, 節] 這條路徑（由外而內）。 */
export function navPath(subjectId: string, nodeId: string): GuideNavNode[] {
  const guide = guideNav.guides[subjectId]
  if (!guide) return []
  const path: GuideNavNode[] = []
  let current: GuideNavNode | undefined = guide.nodesById[nodeId]
  // parentId 由資料產生器保證無環，仍加上長度上限以防資料異常時卡住渲染
  while (current && path.length < 16) {
    path.unshift(current)
    current = current.parentId ? guide.nodesById[current.parentId] : undefined
  }
  return path
}

/**
 * 組出「級別 › 科目 › 第三章 … › 節」。
 * 級別與科目一律從 toc_manifest 衍生的 resourceLevels 來——章節定義的 SSOT 是
 * toc_manifest，導覽樹只負責補「章以下」。
 */
export function guideBreadcrumb(subjectId: string, nodeId: string): BreadcrumbCrumb[] {
  const level = resourceLevels.find((lvl) => lvl.subjects.some((s) => s.id === subjectId))
  const subject = level?.subjects.find((s) => s.id === subjectId)

  const crumbs: BreadcrumbCrumb[] = []
  if (level) crumbs.push({ label: level.label })
  if (subject) {
    crumbs.push({ label: subject.shortLabel || subject.label, to: subject.overviewTo })
  }
  for (const node of navPath(subjectId, nodeId)) {
    crumbs.push({ label: node.title, to: node.route ?? undefined })
  }
  return crumbs
}
