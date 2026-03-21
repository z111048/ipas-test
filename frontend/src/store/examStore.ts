import { create } from 'zustand'
import type { ExamData, ExamPhase, UserAnswers } from '../types'

interface ExamState {
  phase: ExamPhase
  examData: ExamData | null
  examKey: string
  userAnswers: UserAnswers
  secondsRemaining: number

  setExam: (data: ExamData, key: string) => void
  startExam: () => void
  selectAnswer: (index: number, key: 'A' | 'B' | 'C' | 'D') => void
  submitExam: () => void
  resetExam: () => void
  tickTimer: () => void
}

export const useExamStore = create<ExamState>((set) => ({
  phase: 'intro',
  examData: null,
  examKey: '',
  userAnswers: {},
  secondsRemaining: 90 * 60,

  setExam: (data, key) => {
    const minutes = parseInt(data.time_limit) || 90
    set({
      phase: 'intro',
      examData: data,
      examKey: key,
      userAnswers: {},
      secondsRemaining: minutes * 60,
    })
  },

  startExam: () => {
    set((s) => ({
      phase: 'active',
      userAnswers: {},
      secondsRemaining: parseInt(s.examData?.time_limit ?? '90') * 60 || 90 * 60,
    }))
  },

  selectAnswer: (index, key) => {
    set((s) => ({
      userAnswers: { ...s.userAnswers, [index]: key },
    }))
  },

  submitExam: () => {
    set({ phase: 'results' })
  },

  resetExam: () => {
    set((s) => ({
      phase: 'intro',
      userAnswers: {},
      secondsRemaining: parseInt(s.examData?.time_limit ?? '90') * 60 || 90 * 60,
    }))
  },

  tickTimer: () => {
    set((s) => ({ secondsRemaining: s.secondsRemaining - 1 }))
  },
}))
