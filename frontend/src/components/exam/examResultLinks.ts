import { guideNav, navPath } from '../../data/guideNav'
import { examByRouteKey } from '../../data/resourceCatalog'
import { resourceLevels, resourceSummary } from '../../data/resourceRegistry'
import type { ExamReferenceCitation } from '../../types'

/**
 * 成績頁的站內連結：參考詳解的引用 → 學習指引錨點；錯題 → 相關章節練習。
 * 章節一律從 guideNav（由 toc_manifest 衍生）與 resourceLevels 查，不硬編章節。
 */

function subjectIdsForNode(nodeId: string, preferredSubjectId?: string | null) {
  const ids = Object.keys(guideNav.guides)
  const ordered = preferredSubjectId && ids.includes(preferredSubjectId)
    ? [preferredSubjectId, ...ids.filter((id) => id !== preferredSubjectId)]
    : ids
  return ordered.filter((id) => Boolean(guideNav.guides[id]?.nodesById[nodeId]))
}

/** 引用能對到學習指引節點時回傳 `/guide/:subjectId/:nodeId#block`；對不到回傳 undefined（保留純文字）。 */
export function citationRoute(citation: ExamReferenceCitation, preferredSubjectId?: string | null) {
  const subjectId = subjectIdsForNode(citation.node_id, preferredSubjectId)[0]
  if (!subjectId) return undefined
  const block = citation.block_ids?.[0]
  return `/guide/${subjectId}/${citation.node_id}${block ? `#${encodeURIComponent(block)}` : ''}`
}

export function examSubjectId(examKey: string) {
  return examByRouteKey(examKey)?.subjectId ?? null
}

interface PracticeChapter {
  subjectId: string
  chapterId: string
  title: string
}

function practiceChapterForNode(nodeId: string, preferredSubjectId?: string | null): PracticeChapter | undefined {
  for (const subjectId of subjectIdsForNode(nodeId, preferredSubjectId)) {
    const level = resourceLevels.find((item) => item.subjects.some((subject) => subject.id === subjectId))
    if (!level) continue
    const tocSubject = level.toc.subjects.find((subject) => subject.id === subjectId)
    const counts = resourceSummary.levels[level.id]?.subjects[subjectId]?.ai?.chapterCounts ?? {}
    // 引用可能落在「節」；沿導覽樹往上找到 toc 章節。
    const candidates = [nodeId, ...navPath(subjectId, nodeId).map((node) => node.id)]
    for (const candidate of candidates) {
      const chapter = tocSubject?.chapters.find((item) => item.id === candidate)
      if (chapter && (counts[chapter.id] ?? 0) > 0) {
        return { subjectId, chapterId: chapter.id, title: chapter.title }
      }
    }
  }
  return undefined
}

export interface NextStepTarget {
  to: string
  label: string
}

/**
 * 「下一步」要回去練的章節：取各題參考詳解引用中最常出現、且有章節練習題的章節。
 * 找不到就回科目總覽；連科目都推不出來時回傳 undefined。
 */
export function relatedPracticeTarget(
  citationsPerQuestion: ExamReferenceCitation[][],
  preferredSubjectId?: string | null,
): NextStepTarget | undefined {
  const tally = new Map<string, { chapter: PracticeChapter; count: number; firstSeen: number }>()
  let order = 0
  for (const citations of citationsPerQuestion) {
    // 每題只算一次：取第一個能對到練習章節的引用（引用依相關度排序）。
    for (const citation of citations) {
      const chapter = practiceChapterForNode(citation.node_id, preferredSubjectId)
      if (!chapter) continue
      const key = `${chapter.subjectId}/${chapter.chapterId}`
      const entry = tally.get(key)
      if (entry) entry.count += 1
      else tally.set(key, { chapter, count: 1, firstSeen: order++ })
      break
    }
  }
  const best = [...tally.values()].sort((a, b) => b.count - a.count || a.firstSeen - b.firstSeen)[0]
  if (best) {
    return {
      to: `/practice/${best.chapter.subjectId}/${best.chapter.chapterId}`,
      label: `回到相關章節練習：${best.chapter.title}`,
    }
  }

  const subjectId = preferredSubjectId
    ?? citationsPerQuestion.flat().map((citation) => subjectIdsForNode(citation.node_id)[0]).find(Boolean)
  const subject = subjectId
    ? resourceLevels.flatMap((level) => level.subjects).find((item) => item.id === subjectId)
    : undefined
  if (subject?.overviewTo) {
    return { to: subject.overviewTo, label: `回到科目總覽（${subject.shortLabel}）` }
  }
  return undefined
}
