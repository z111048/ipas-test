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
  page_range?: [number, number] | null
  source_pages?: GuideSourcePage[]
}

export interface GuideSourcePage {
  index: number
  page: number
  label?: string
  image: string
}

export interface GuideData {
  subject: string
  chapters: GuideChapter[]
}

export interface GuideOutlineNode {
  id: string
  parentId: string | null
  depth: number
  order: number
  title: string
  number?: string | null
  pageLabel: string
  pageRange: [number, number]
  route: string
  contentRef: string
  children: string[]
}

export interface GuideContent {
  id: string
  title: string
  content: string
  contentFormat: 'plain' | 'markdown'
  sourcePages: GuideSourcePage[]
}

export interface GuideOutlineSubject {
  subjectId: string
  key: string
  subject: string
  pdf: string
  root: string[]
  nodesById: Record<string, GuideOutlineNode>
  flat: string[]
  stats: Record<string, number>
}

export interface GuideOutlinesData {
  level: string
  guides: Record<string, GuideOutlineSubject>
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

export interface PdfImageAsset {
  id: string
  key: string
  pdf: string
  type: 'page' | 'image' | 'table'
  asset_id: string
  page_index: number
  page_number: number
  page_label: string
  bbox: number[]
  path: string
}

export interface PdfImageGallery {
  level: string
  total: number
  items: PdfImageAsset[]
}
