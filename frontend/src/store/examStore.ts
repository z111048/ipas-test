import { create } from 'zustand'
import type { ExamData, ExamPhase, UserAnswers } from '../types'

/**
 * 作答中的考卷存在 localStorage，切到別頁或重新整理都不會掉。
 *
 * 計時語意是「離開即暫停」：存的是剩餘秒數，回來按「繼續」時才以當下時間重設截止時間。
 * 停留在本頁（含背景分頁）仍以絕對截止時間計時，見 useExamTimer。
 *
 * 只存 phase === 'active' 的作答；交卷（含時間到）、重新開始、重新考試都會清掉。
 * 版本號不符、examKey 不符或欄位型別不對的舊資料一律忽略。
 */
const ATTEMPT_VERSION = 1

export function examAttemptStorageKey(examKey: string) {
  return `ipas:exam:${examKey}:attempt`
}

export interface SavedExamAttempt {
  v: typeof ATTEMPT_VERSION
  examKey: string
  phase: 'active'
  answers: UserAnswers
  currentIndex: number
  secondsRemaining: number
  startedAt: number
  savedAt: number
}

const OPTION_KEYS = new Set(['A', 'B', 'C', 'D'])

function timeLimitSeconds(data: ExamData | null) {
  return parseInt(data?.time_limit ?? '90') * 60 || 90 * 60
}

function readSavedAttempt(examKey: string, data: ExamData): SavedExamAttempt | null {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(examAttemptStorageKey(examKey))
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<SavedExamAttempt> | null
    if (!parsed || parsed.v !== ATTEMPT_VERSION || parsed.examKey !== examKey || parsed.phase !== 'active') {
      return null
    }
    const limit = timeLimitSeconds(data)
    const seconds = parsed.secondsRemaining
    if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) return null
    const ids = new Set(data.questions.map((q) => q.id))
    const answers: UserAnswers = {}
    if (parsed.answers && typeof parsed.answers === 'object') {
      for (const [id, key] of Object.entries(parsed.answers)) {
        if (ids.has(id) && typeof key === 'string' && OPTION_KEYS.has(key)) {
          answers[id] = key as UserAnswers[string]
        }
      }
    }
    const index = typeof parsed.currentIndex === 'number' && Number.isInteger(parsed.currentIndex)
      ? Math.max(0, Math.min(parsed.currentIndex, data.questions.length - 1))
      : 0
    return {
      v: ATTEMPT_VERSION,
      examKey,
      phase: 'active',
      answers,
      currentIndex: index,
      secondsRemaining: Math.min(Math.ceil(seconds), limit),
      startedAt: typeof parsed.startedAt === 'number' ? parsed.startedAt : Date.now(),
      savedAt: typeof parsed.savedAt === 'number' ? parsed.savedAt : Date.now(),
    }
  } catch {
    return null
  }
}

function writeAttempt(attempt: SavedExamAttempt) {
  try {
    window.localStorage.setItem(examAttemptStorageKey(attempt.examKey), JSON.stringify(attempt))
  } catch {
    // 容量已滿或無痕模式：只是失去續答能力，不影響作答
  }
}

function clearAttempt(examKey: string) {
  if (!examKey) return
  try {
    window.localStorage.removeItem(examAttemptStorageKey(examKey))
  } catch {
    // ignore
  }
}

function remainingAt(deadlineMs: number | null, fallback: number, nowMs = Date.now()) {
  if (deadlineMs === null) return fallback
  return Math.max(0, Math.ceil((deadlineMs - nowMs) / 1000))
}

interface ExamState {
  phase: ExamPhase
  examData: ExamData | null
  examKey: string
  userAnswers: UserAnswers
  secondsRemaining: number
  deadlineMs: number | null
  /** 當前題（scroll-spy 的 activeIndex），只為了續答時回到同一題。 */
  currentIndex: number
  startedAt: number | null
  /** intro 階段可續答的上次作答；null 表示沒有。 */
  savedAttempt: SavedExamAttempt | null

  setExam: (data: ExamData, key: string) => void
  /** 開始新的作答；若有上次作答會被丟棄（「重新開始」也走這裡）。 */
  startExam: () => void
  resumeExam: () => void
  /** 離開考試頁時呼叫：作答中就存檔並退回 intro，回來時可選擇續答。 */
  suspendExam: () => void
  selectAnswer: (questionId: string, key: 'A' | 'B' | 'C' | 'D') => void
  setCurrentIndex: (index: number) => void
  submitExam: () => void
  resetExam: () => void
  syncTimer: (nowMs?: number) => void
}

export const useExamStore = create<ExamState>((set) => ({
  phase: 'intro',
  examData: null,
  examKey: '',
  userAnswers: {},
  secondsRemaining: 90 * 60,
  deadlineMs: null,
  currentIndex: 0,
  startedAt: null,
  savedAttempt: null,

  setExam: (data, key) => {
    set({
      phase: 'intro',
      examData: data,
      examKey: key,
      userAnswers: {},
      secondsRemaining: timeLimitSeconds(data),
      deadlineMs: null,
      currentIndex: 0,
      startedAt: null,
      savedAttempt: readSavedAttempt(key, data),
    })
  },

  startExam: () => {
    set((s) => {
      clearAttempt(s.examKey)
      const seconds = timeLimitSeconds(s.examData)
      const now = Date.now()
      return {
        phase: 'active',
        userAnswers: {},
        secondsRemaining: seconds,
        deadlineMs: now + seconds * 1000,
        currentIndex: 0,
        startedAt: now,
        savedAttempt: null,
      }
    })
  },

  resumeExam: () => {
    set((s) => {
      const saved = s.savedAttempt
      if (!saved || saved.examKey !== s.examKey) return s
      return {
        phase: 'active',
        userAnswers: { ...saved.answers },
        secondsRemaining: saved.secondsRemaining,
        deadlineMs: Date.now() + saved.secondsRemaining * 1000,
        currentIndex: saved.currentIndex,
        startedAt: saved.startedAt,
        savedAttempt: null,
      }
    })
  },

  suspendExam: () => {
    set((s) => {
      if (s.phase !== 'active' || !s.examKey) return s
      const seconds = remainingAt(s.deadlineMs, s.secondsRemaining)
      if (seconds === 0) {
        clearAttempt(s.examKey)
        return { phase: 'results', secondsRemaining: 0, deadlineMs: null }
      }
      const now = Date.now()
      const attempt: SavedExamAttempt = {
        v: ATTEMPT_VERSION,
        examKey: s.examKey,
        phase: 'active',
        answers: s.userAnswers,
        currentIndex: s.currentIndex,
        secondsRemaining: seconds,
        startedAt: s.startedAt ?? now,
        savedAt: now,
      }
      writeAttempt(attempt)
      return {
        phase: 'intro',
        userAnswers: {},
        secondsRemaining: timeLimitSeconds(s.examData),
        deadlineMs: null,
        currentIndex: 0,
        startedAt: null,
        savedAttempt: attempt,
      }
    })
  },

  selectAnswer: (questionId, key) => {
    set((s) => ({
      userAnswers: { ...s.userAnswers, [questionId]: key },
    }))
  },

  setCurrentIndex: (index) => {
    set((s) => (s.currentIndex === index ? s : { currentIndex: index }))
  },

  submitExam: () => {
    set((s) => {
      clearAttempt(s.examKey)
      return { phase: 'results', deadlineMs: null, savedAttempt: null }
    })
  },

  resetExam: () => {
    set((s) => {
      clearAttempt(s.examKey)
      return {
        phase: 'intro',
        userAnswers: {},
        secondsRemaining: timeLimitSeconds(s.examData),
        deadlineMs: null,
        currentIndex: 0,
        startedAt: null,
        savedAttempt: null,
      }
    })
  },

  syncTimer: (nowMs = Date.now()) => {
    set((s) => {
      if (s.phase !== 'active' || s.deadlineMs === null) return s
      const secondsRemaining = remainingAt(s.deadlineMs, s.secondsRemaining, nowMs)
      if (secondsRemaining === 0) {
        clearAttempt(s.examKey)
        return { secondsRemaining: 0, phase: 'results', deadlineMs: null }
      }
      // 秒數沒變就不產生新 state，避免無謂的 re-render 與 storage 寫入
      if (secondsRemaining === s.secondsRemaining) return s
      return { secondsRemaining }
    })
  },
}))

// 作答中的任何變動（作答、換題、每秒倒數）都同步寫入 storage。
// 只在 active 時寫；離開 active 的清除由各 action 明確處理，
// 這樣切到另一份考卷（setExam 把 phase 設回 intro）不會誤刪上一份的進度。
useExamStore.subscribe((s, prev) => {
  if (s.phase !== 'active' || !s.examKey) return
  if (
    s.phase === prev.phase
    && s.examKey === prev.examKey
    && s.userAnswers === prev.userAnswers
    && s.currentIndex === prev.currentIndex
    && s.secondsRemaining === prev.secondsRemaining
  ) return
  writeAttempt({
    v: ATTEMPT_VERSION,
    examKey: s.examKey,
    phase: 'active',
    answers: s.userAnswers,
    currentIndex: s.currentIndex,
    secondsRemaining: s.secondsRemaining,
    startedAt: s.startedAt ?? Date.now(),
    savedAt: Date.now(),
  })
})
