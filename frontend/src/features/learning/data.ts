import type { Hash, Lab, LearningPath, LearningUnit, Project, ReleaseManifest } from './types'

export type LearningKind = 'learning-unit' | 'learning-path' | 'project' | 'lab' | 'mock-blueprint' | 'mock-pool' | 'exam-analysis' | 'assembly-result'
export type LearningDirectory = 'units' | 'paths' | 'projects' | 'labs' | 'blueprints' | 'pools' | 'analysis' | 'assemblies'

export interface LearningMeta {
  id: string
  revision: number
  title: string
  chapterRefs: Array<{ levelId: 'junior' | 'middle'; subjectId: string; chapterId: string }>
  path: string
  summary?: string
}

export interface LearningIndex {
  schemaVersion: 1
  releaseId: string
  availability: 'preview' | 'published'
  units: LearningMeta[]
  paths: LearningMeta[]
  projects: LearningMeta[]
  labs: LearningMeta[]
  blueprints: LearningMeta[]
  pools: LearningMeta[]
  analysis: LearningMeta[]
  assemblies: LearningMeta[]
}

export interface LearningItem<T> {
  releaseId: string
  availability: 'preview' | 'published'
  kind: LearningKind
  document: T
  bodyMarkdown?: string
  assetLocations?: Array<{ variant: 'starter' | 'solution'; path: string; hash: string; size: number }>
  supportAssets?: Array<{ label: string; path: string; hash: string; size: number }>
  sourceExamples?: SourceExample[]
  questionPaths?: Record<string, string>
}

export interface SourceExample {
  question: { questionKey: string; revision: number; hash: Hash }
  questionPath: string
  stem: string
  unitId: string
  relation: 'explained_by' | 'prerequisite'
  reason: string
  source: { levelId: 'junior' | 'middle'; examKey: string; pageIndex: number; pageNumber: number; route: string }
}

export interface QuestionRevision {
  questionKey: string
  revision: number
  contentHash: Hash
  format: 'single_choice'
  stem: string
  options: Array<{ optionId: string; text: string }>
  correctOptionId: string
  explanation: string
  answerStatus: 'legacy_unverified' | 'verified' | 'disputed' | 'withdrawn'
}

export interface QuestionIndex {
  releaseId: string
  questions: Array<{ questionKey: string; revision: number; contentHash: string; path: string }>
}

export interface MockPool {
  schemaVersion: 1
  id: string
  releaseId: string
  contentHash: Hash
  questions: Array<{ question: { questionKey: string; revision: number; hash: Hash }; payloadPath: string; fileHash: Hash }>
}

export interface MockBlueprint {
  id: string
  revision: number
  contentHash: Hash
  title: string
  questionCount: number
  timeLimitSeconds: number
  poolRef: { id: string; releaseId: string; hash: Hash }
  algorithmVersion: 'mock-selector-v1'
  optionOrder: 'fixed' | 'seeded'
  scoring: { correct: number; incorrect: 0; unanswered: 0; passingPercent: number }
}

export interface ReadyAssembly {
  status: 'ready'
  formId: string
  seed: string
  blueprintHash: Hash
  poolRef: { id: string; releaseId: string; hash: Hash }
  poolHash: Hash
  selectedQuestionRevisions: Array<{ questionKey: string; revision: number; hash: Hash }>
  slotAssignments: Array<{ question: { questionKey: string; revision: number; hash: Hash }; dimension: 'topic' | 'chapter' | 'difficulty'; quotaId: string }>
  displayedOptionIds: Array<{ question: { questionKey: string; revision: number; hash: Hash }; optionIds: string[] }>
  softMisses: string[]
}

type LearningDocument = LearningUnit | LearningPath | Project | Lab | MockBlueprint | MockPool | ReadyAssembly | Record<string, unknown>
type JsonModule<T> = { default: T }

const productionPointers = import.meta.glob<JsonModule<{ releaseId: string; manifestPath: string }>>('../../generated/learning/current.json')
const productionJson = import.meta.glob<JsonModule<unknown>>('../../generated/learning/releases/**/*.json')

let indexPromise: Promise<LearningIndex | null> | undefined
let releaseBase = ''

async function loadDevJson<T>(relativePath: string): Promise<T> {
  const response = await fetch(`/src/generated/learning/${relativePath}`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`學習內容載入失敗（${response.status}）`)
  return response.json() as Promise<T>
}

function productionKey(relativePath: string) {
  return `../../generated/learning/${relativePath}`
}

async function loadProductionJson<T>(relativePath: string): Promise<T> {
  const loader = productionJson[productionKey(relativePath)]
  if (!loader) throw new Error('找不到這個版本的學習內容')
  return (await loader() as JsonModule<T>).default
}

async function resolveIndex(): Promise<LearningIndex | null> {
  if (import.meta.env.DEV) {
    try {
      const pointer = await loadDevJson<{ availability: 'preview'; releaseId: string; manifestPath: string }>('preview.json')
      if (pointer.availability !== 'preview') throw new Error('預覽指標格式錯誤')
      const manifest = await loadDevJson<ReleaseManifest>(pointer.manifestPath)
      if (manifest.releaseId !== pointer.releaseId || manifest.availability !== 'preview') throw new Error('預覽版本指標已失效')
      releaseBase = pointer.manifestPath.replace(/manifest\.json$/, '')
      const index = await loadDevJson<LearningIndex>(`${releaseBase}index.json`)
      if (index.releaseId !== pointer.releaseId || index.availability !== 'preview') throw new Error('預覽索引版本不一致')
      return index
    } catch (error) {
      if (error instanceof TypeError || (error instanceof Error && error.message.includes('404'))) return null
      throw error
    }
  }

  const pointerLoader = productionPointers['../../generated/learning/current.json']
  if (!pointerLoader) return null
  const pointer = (await pointerLoader()).default
  releaseBase = pointer.manifestPath.replace(/manifest\.json$/, '')
  const manifest = await loadProductionJson<ReleaseManifest>(pointer.manifestPath)
  if (manifest.releaseId !== pointer.releaseId || manifest.availability !== 'published') throw new Error('正式學習內容版本不一致')
  return loadProductionJson<LearningIndex>(`${releaseBase}index.json`)
}

export function loadLearningIndex(refresh = false): Promise<LearningIndex | null> {
  if (refresh) indexPromise = undefined
  indexPromise ??= resolveIndex().catch((error) => {
    indexPromise = undefined
    throw error
  })
  return indexPromise
}

export async function loadLearningItem<T extends LearningDocument>(path: string): Promise<LearningItem<T>> {
  await loadLearningIndex()
  if (!releaseBase) throw new Error('目前沒有可用的學習內容')
  return import.meta.env.DEV
    ? loadDevJson<LearningItem<T>>(`${releaseBase}${path}`)
    : loadProductionJson<LearningItem<T>>(`${releaseBase}${path}`)
}

export async function loadQuestionIndex(): Promise<QuestionIndex> {
  await loadLearningIndex()
  if (!releaseBase) throw new Error('目前沒有可用的題目版本')
  return import.meta.env.DEV
    ? loadDevJson<QuestionIndex>(`${releaseBase}question-index.json`)
    : loadProductionJson<QuestionIndex>(`${releaseBase}question-index.json`)
}

export async function loadQuestion(path: string): Promise<QuestionRevision> {
  await loadLearningIndex()
  if (!releaseBase) throw new Error('目前沒有可用的題目版本')
  return import.meta.env.DEV
    ? loadDevJson<QuestionRevision>(`${releaseBase}${path}`)
    : loadProductionJson<QuestionRevision>(`${releaseBase}${path}`)
}

export async function learningAssetUrl(path: string): Promise<string> {
  await loadLearningIndex()
  if (!releaseBase) throw new Error('目前沒有可用的 Lab 資產')
  if (!import.meta.env.DEV) return path
  return `/src/generated/learning/${releaseBase}${path}`
}

export function findMeta(index: LearningIndex, directory: LearningDirectory, id: string) {
  return (index[directory] ?? []).find((item) => item.id === id)
}
