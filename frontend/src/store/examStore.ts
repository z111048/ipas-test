import { create } from 'zustand'
import type { ExamData, ExamPhase, UserAnswers } from '../types'

interface ExamState {
  phase: ExamPhase
  examData: ExamData | null
  examKey: string
  userAnswers: UserAnswers
  secondsRemaining: number
  deadlineMs: number | null

  setExam: (data: ExamData, key: string) => void
  startExam: () => void
  selectAnswer: (questionId: string, key: 'A' | 'B' | 'C' | 'D') => void
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

  setExam: (data, key) => {
    const minutes = parseInt(data.time_limit) || 90
    set({
      phase: 'intro',
      examData: data,
      examKey: key,
      userAnswers: {},
      secondsRemaining: minutes * 60,
      deadlineMs: null,
    })
  },

  startExam: () => {
    set((s) => {
      const seconds = parseInt(s.examData?.time_limit ?? '90') * 60 || 90 * 60
      return {
        phase: 'active',
        userAnswers: {},
        secondsRemaining: seconds,
        deadlineMs: Date.now() + seconds * 1000,
      }
    })
  },

  selectAnswer: (questionId, key) => {
    set((s) => ({
      userAnswers: { ...s.userAnswers, [questionId]: key },
    }))
  },

  submitExam: () => {
    set({ phase: 'results', deadlineMs: null })
  },

  resetExam: () => {
    set((s) => ({
      phase: 'intro',
      userAnswers: {},
      secondsRemaining: parseInt(s.examData?.time_limit ?? '90') * 60 || 90 * 60,
      deadlineMs: null,
    }))
  },

  syncTimer: (nowMs = Date.now()) => {
    set((s) => {
      if (s.phase !== 'active' || s.deadlineMs === null) return s
      const secondsRemaining = Math.max(0, Math.ceil((s.deadlineMs - nowMs) / 1000))
      if (secondsRemaining === 0) {
        return { secondsRemaining: 0, phase: 'results', deadlineMs: null }
      }
      return { secondsRemaining }
    })
  },
}))
