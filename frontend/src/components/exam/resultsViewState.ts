/**
 * 成績頁的檢視狀態（篩選、已展開的解析、捲動位置）在離開成績頁後保留。
 *
 * 考生在成績頁點「學習指引對應段落」會換路由、ExamResults 會 unmount；
 * 按上一頁或「回到考試成績」回來時，要回到原本的篩選、展開與那一題的位置。
 *
 * 只存在記憶體裡（和 examStore 的成績同一個生命週期）：重新整理後成績本身也不在了。
 * 用 userAnswers 物件的 identity 辨識「同一次交卷」，重新作答會產生新物件，舊狀態自然失效。
 */
export type ResultFilter = 'all' | 'wrong' | 'skipped'

export interface ResultsViewAnchor {
  /** 題目在試卷中的 index（對應 `#result-q-{index}`）。 */
  questionIndex: number
  /** 該題卡片頂端距離捲動容器頂端的距離（px），回來時對齊到同一位置。 */
  offset: number
  /** 點擊的引用連結路徑，回來時把焦點還給它。 */
  to?: string
}

export interface ResultsViewState {
  examKey: string
  answers: unknown
  filter: ResultFilter
  expanded: ReadonlySet<string>
  anchor: ResultsViewAnchor | null
}

let saved: ResultsViewState | null = null

export function readResultsView(examKey: string | null, answers: unknown): ResultsViewState | null {
  if (!saved || !examKey || saved.examKey !== examKey || saved.answers !== answers) return null
  return saved
}

export function writeResultsView(state: ResultsViewState) {
  saved = state
}

/** 回來後已經捲到原位，清掉錨點，之後再進成績頁（例如從別頁點側欄）不會又跳一次。 */
export function consumeResultsAnchor() {
  if (saved) saved = { ...saved, anchor: null }
}

export function clearResultsView() {
  saved = null
}

/** 從成績頁前往學習指引時帶在 router location state 裡，讓指引頁顯示「回到考試成績」。 */
export interface ExamResultsReturnState {
  examResultsReturn: { to: string }
}

export function examResultsReturnTarget(state: unknown): string | null {
  if (!state || typeof state !== 'object') return null
  const value = (state as Partial<ExamResultsReturnState>).examResultsReturn
  return value && typeof value.to === 'string' && value.to.startsWith('/exam/') ? value.to : null
}
