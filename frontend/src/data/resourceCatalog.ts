import catalogRaw from '@catalog/resource_catalog.json'

export type ResourceLevelId = 'junior' | 'middle'
export type CatalogExamKind = 'official' | 'sample'

export interface CatalogLevel {
  id: ResourceLevelId
  dataLevel: string
  label: string
  subtitle: string
}

export interface CatalogExam {
  key: string
  routeKey: string
  levelId: ResourceLevelId
  kind: CatalogExamKind
  subjectId: string | null
  pdf: string
  questionFile: string
  title: string
  label: string
  expectedQuestions: number
  guideKeys: string[]
  aliases?: string[]
  legacyReferencePrefix?: string
  legacyAssetKey?: string
}

export interface CatalogResource {
  key: string
  kind: 'pdf' | 'route'
  visibleIn: ResourceLevelId[]
  label: string
  detail?: string
  sourceLevel?: string
  sourceKey?: string
  pdf?: string
  route?: string
}

export interface ResourceCatalog {
  schemaVersion: 1
  levels: CatalogLevel[]
  exams: CatalogExam[]
  resources: CatalogResource[]
}

export const resourceCatalog = catalogRaw as unknown as ResourceCatalog

if (resourceCatalog.schemaVersion !== 1) {
  throw new Error(`Unsupported resource catalog schema: ${resourceCatalog.schemaVersion}`)
}

export const catalogLevels = resourceCatalog.levels
export const catalogExams = resourceCatalog.exams

export function examsForLevel(levelId: ResourceLevelId) {
  return catalogExams.filter((exam) => exam.levelId === levelId)
}

export function resourcesForLevel(levelId: ResourceLevelId) {
  return resourceCatalog.resources.filter((resource) => resource.visibleIn.includes(levelId))
}

export function examByRouteKey(routeKey: string) {
  return catalogExams.find((exam) => exam.routeKey === routeKey)
}
