export interface QuestionCard {
  concept: string
  mnemonic: string
  confusion: string
  frequency: '高' | '中' | '低'
}

export interface QuestionImage {
  type: 'page' | 'image'
  src: string
  alt: string
  page_index: number
  page_number: number
  bbox?: number[]
  placement?: 'question' | 'option' | 'context'
  option?: 'A' | 'B' | 'C' | 'D'
  markdown?: string
  markdown_language?: string
  markdown_title?: string
}

export interface QuestionContextBlock {
  title?: string
  language?: string
  markdown: string
}

export interface Question {
  id: string
  context?: string
  context_blocks?: QuestionContextBlock[]
  question: string
  options: Record<'A' | 'B' | 'C' | 'D', string>
  answer: 'A' | 'B' | 'C' | 'D'
  explanation: string
  images?: QuestionImage[]
  card?: QuestionCard
  difficulty?: '易' | '中' | '難'
  type?: string
  tags?: string[]
  source?: string
  source_ref?: {
    page_index: number
    page_number: number
  }
}

export interface ExamReferenceCitation {
  guide_key: string
  node_id: string
  title: string
  page_label?: string | null
  block_ids?: string[]
  why_relevant?: string
}

export interface ExamReferenceAnswer {
  answer: 'A' | 'B' | 'C' | 'D'
  reference_answer: string
  option_analysis?: Partial<Record<'A' | 'B' | 'C' | 'D', string>>
  key_concepts?: string[]
  citations?: ExamReferenceCitation[]
  confidence?: 'high' | 'medium' | 'low'
  notes?: string
}

export interface GuideExamAnnotation {
  id: string
  examKey: string
  examLabel: string
  examTitle: string
  route: string
  questionId: string
  referenceQuestionId?: string
  questionNumber: number
  question: string
  answer: 'A' | 'B' | 'C' | 'D'
  confidence?: 'high' | 'medium' | 'low'
  reasons?: string[]
}

export interface GuideExamAnnotationsChapterData {
  guideKey: string
  nodeId: string
  stats: {
    questions: number
    guideBlocks: number
    annotations: number
  }
  blocks: Record<string, GuideExamAnnotation[]>
}

export interface GuideExamAnnotationsIndexData {
  source: string
  scope: 'officialPastExams'
  stats: {
    exams: number
    questions: number
    guideNodes: number
    guideBlocks: number
    annotations: number
    missingQuestions: number
    missingBlocks: number
  }
  byGuide: Record<string, Record<string, {
    questions: number
    guideBlocks: number
    annotations: number
  }>>
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
  tables?: GuideSourceTable[]
}

export interface GuideSourceTable {
  id: string
  bbox: number[]
  image?: string
  rows: string[][]
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
  headings?: Array<{
    id: string
    level: number
    title: string
  }>
  blocks?: GuideBlock[]
  sourcePages: GuideSourcePage[]
}

export interface GuideImageAsset {
  id: string
  level: string
  subjectId: string
  guideKey: string
  sourceNodeId: string
  headingBlockId: string | null
  headingDepth: number | null
  title: string
  headingPath: string[]
  pageNumbers: number[]
  src: string
  output: string
}

export interface GuideImagesData {
  source: string
  totalImages: number
  images: GuideImageAsset[]
  byChapter: Record<string, GuideImageAsset[]>
}

export type GuideBlockType = 'heading' | 'paragraph' | 'list_item' | 'table' | 'question' | 'answer' | 'spacer'

export interface GuideFormula {
  latex: string
  display?: boolean
}

export interface GuideBlock {
  id: string
  type: GuideBlockType
  depth: number
  title?: string
  text?: string
  marker?: string
  anchor?: string
  rows?: string[][]
  html?: string
  formulas?: GuideFormula[]
  latex?: string | string[]
  formulaOnly?: boolean
  pageIndex?: number
  bbox?: number[]
  indentFirstLine?: boolean
}

export interface GuideOutlineSubject {
  level?: string
  subjectId: string
  key: string
  sourceKey?: string
  subject: string
  pdf: string
  root: string[]
  nodesById: Record<string, GuideOutlineNode>
  flat: string[]
  stats: Record<string, number>
  treeSource?: string
}

export interface GuideOutlinesData {
  level?: string
  levels?: string[]
  guides: Record<string, GuideOutlineSubject>
}

export type LearningArticleLevelId = 'junior' | 'middle'

export interface LearningArticleSource {
  guideKey: string
  nodeId: string
  contentRef: string
  sourceContentRef?: string
  sourcePageRange?: [number, number] | null
  pdf?: string
}

export interface LearningArticleSection {
  id: string
  title: string
  depth: number
}

export interface LearningArticleMeta {
  id: string
  levelId: LearningArticleLevelId
  levelLabel: string
  subjectId: string
  subjectTitle: string
  subjectShortTitle: string
  title: string
  order: number
  globalOrder: number
  route: string
  guideRoute: string
  practiceRoute: string
  pathIds: string[]
  subtopics: string[]
  excerpt: string
  wordCount: number
  readingMinutes: number
  sectionCount: number
  source: LearningArticleSource
}

export interface LearningArticle extends LearningArticleMeta {
  sections: LearningArticleSection[]
  blocks: GuideBlock[]
}

export interface LearningArticleSubjectIndex {
  id: string
  title: string
  shortTitle: string
  articleIds: string[]
}

export interface LearningArticleLevelIndex {
  id: LearningArticleLevelId
  label: string
  articleIds: string[]
  subjects: LearningArticleSubjectIndex[]
}

export interface LearningPath {
  id: string
  title: string
  description: string
  articleIds: string[]
  articleCount: number
  levelIds: LearningArticleLevelId[]
  estimatedMinutes: number
  route: string
  startingArticleId: string
}

export interface LearningArticleIndex {
  generatedAt: string
  articleCount: number
  pathCount: number
  levels: Record<LearningArticleLevelId, LearningArticleLevelIndex>
  learningPaths: LearningPath[]
  pathsById: Record<string, LearningPath>
  flatArticleIds: string[]
  articlesById: Record<string, LearningArticleMeta>
}

export interface ResourceQuestionSummary {
  available: boolean
  total: number
  firstChapterId: string | null
  chapterCounts: Record<string, number>
}

export interface ResourceExamSummary {
  available: boolean
  total: number
}

export interface ResourceSubjectSummary {
  ai?: ResourceQuestionSummary
  guide?: ResourceQuestionSummary
  codex100?: ResourceQuestionSummary
}

export interface ResourceLevelSummary {
  level: string
  subjects: Record<string, ResourceSubjectSummary>
  exams: Record<string, ResourceExamSummary>
}

export interface VisualsSummary {
  total: number
  byLevel: Record<string, number>
}

export interface ResourceSummaryData {
  levels: Record<'junior' | 'middle', ResourceLevelSummary>
  visuals?: VisualsSummary
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
  level?: string
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
  level?: string
  levels?: string[]
  total: number
  items: PdfImageAsset[]
}

export interface ColabCell {
  type: 'markdown' | 'code'
  title?: string
  explanation?: string
  content: string
}

export interface ColabNotebook {
  chapter_id: string
  chapter_title: string
  colab_url: string
  status?: 'pass' | 'warn'
  cells: ColabCell[]
}

/**
 * 學習指引的完整階層樹（frontend/src/generated/guideHierarchy.json）。
 * 由 scripts/export_guide_hierarchy.py 把 guideOutlines 的章/節與各章內部的標題
 * 接成一棵樹。節以下的節點是既有章節頁裡的錨點，不是獨立路由。
 */
export interface GuideHierarchyNode {
  id: string
  parentId: string | null
  depth: number
  kind: 'chapter' | 'section' | 'heading'
  title: string
  /** 只有章/節節點有；標題節點沿用所屬章節的 route */
  route?: string | null
  /** 節以下才有；對應章節頁裡 heading 區塊的 anchor */
  anchor: string | null
  page: number | null
  /** 只有章/節節點有；標題節點的範圍就是 page 本身 */
  pageRange?: [number, number] | null
  childIds: string[]
  /** heading 節點在原書的標題層級（節=2、N.=3、（N）=4、A.=5、a.=6） */
  headingLevel?: number
  /** 由 guide_ocr 補回、頁面上沒有對應區塊的標題 */
  recovered?: boolean
}

export interface GuideHierarchyGuide {
  level: string
  subjectId: string
  key: string
  rootIds: string[]
  nodesById: Record<string, GuideHierarchyNode>
  flat: string[]
}

export interface GuideHierarchyData {
  guides: Record<string, GuideHierarchyGuide>
}
