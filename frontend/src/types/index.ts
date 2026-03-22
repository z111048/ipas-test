export interface QuestionCard {
  concept: string
  mnemonic: string
  confusion: string
  frequency: '高' | '中' | '低'
}

export interface Question {
  id: string
  question: string
  options: Record<'A' | 'B' | 'C' | 'D', string>
  answer: 'A' | 'B' | 'C' | 'D'
  explanation: string
  card?: QuestionCard
  difficulty?: '易' | '中' | '難'
  type?: string
  tags?: string[]
  source?: string
}

export interface Chapter {
  id: string
  title: string
  questions: Question[]
}

export interface SubjectQuestions {
  subject: string
  chapters: Chapter[]
}

export interface ExamData {
  exam: string
  total: number
  time_limit: string
  passing_score: number
  questions: Question[]
}

export interface GuideSection {
  heading: string
  level: 2 | 3
  content: string
}

export interface GuideChapter {
  id: string
  title: string
  subtopics: string[]
  content: string
  sections?: GuideSection[]
  content_format?: 'plain' | 'markdown'
}

export interface GuideData {
  subject: string
  chapters: GuideChapter[]
}

export type UserAnswers = Record<number, 'A' | 'B' | 'C' | 'D'>
export type ExamPhase = 'intro' | 'active' | 'results'

// TOC manifest — single source of truth for chapter definitions
export interface TocChapter {
  id: string
  title: string
  start_page: string
  page_range: [number, number] | null
  subtopics: string[]
}

export interface TocSubject {
  id: string
  key: string
  pdf: string
  subject: string
  chapters: TocChapter[]
}

export interface TocManifest {
  generated_at: string
  subjects: TocSubject[]
}
