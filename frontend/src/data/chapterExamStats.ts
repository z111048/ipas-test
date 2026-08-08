import { loadMindmap } from './guideMindmap'

/**
 * 解說圖卡第四格用的章節考題統計。
 *
 * 原本這一格是 `card.frequency`（高／中／低），2026-08-08 量出它與唯一的客觀依據
 * （該章實際考古題數）**秩相關 −0.173**——方向是反的，判別力接近零，所以整欄移除，
 * 改成可驗證的事實。詳見 `playbook/08-topic-labeling.md` §7-6。
 *
 * 數字直接查 `guideMindmap/{subjectId}.json`（章節熱度圖的同一份產物），
 * **不複製到 689 個題目 JSON 裡**——複製的數字會在熱度重算後靜靜過期。
 */
export interface ChapterExamStat {
  /** 該章命中的相異考古題數 */
  questions: number
  /** 在本科目「學習指引章」中的熱度名次（1 起算） */
  rank: number
  /** 本科目有統計的學習指引章數 */
  total: number
  subject: string
}

/** 官方大綱章（`*pdf-c{n}`）與學習指引章是同一份內容的兩套層級，排名只算後者。 */
const OUTLINE_NODE = /pdf-c\d+$/
const QUESTION_ID = /^(mid-)?(s\d+)(c\d+)/

const cache = new Map<string, ChapterExamStat | null>()

/** `s1c1q1` → `{subjectId: 's1', chapterId: 's1c1'}`；`mid-s2c6q1_codex100` → `mid-s2` / `mid-s2c6`。 */
function parse(questionId: string): { subjectId: string; chapterId: string } | null {
  const match = QUESTION_ID.exec(questionId)
  if (!match) return null
  const prefix = match[1] ?? ''
  return {
    subjectId: `${prefix}${match[2]}`,
    chapterId: `${prefix}${match[2]}${match[3]}`,
  }
}

export async function loadChapterExamStat(
  questionId: string,
): Promise<ChapterExamStat | null> {
  const parsed = parse(questionId)
  if (!parsed) return null
  const hit = cache.get(parsed.chapterId)
  if (hit !== undefined) return hit

  let stat: ChapterExamStat | null = null
  try {
    const data = await loadMindmap(parsed.subjectId)
    const scored = data.nodes
      .filter((node) => node.q !== null && !OUTLINE_NODE.test(node.i))
      .sort((a, b) => (b.q ?? 0) - (a.q ?? 0))
    const index = scored.findIndex((node) => node.i === parsed.chapterId)
    if (index >= 0) {
      stat = {
        questions: scored[index].q ?? 0,
        rank: index + 1,
        total: scored.length,
        subject: data.subject.replace(/^(中級)?科目.*?：/, '') || data.subject,
      }
    }
  } catch {
    stat = null // 查不到就不顯示這一格，不要顯示 0 題
  }
  cache.set(parsed.chapterId, stat)
  return stat
}
