import type { ExamData } from '../types'
import { catalogExams, type ResourceLevelId } from './resourceCatalog'

type JsonModule = { default: unknown }

const questionModules: Record<ResourceLevelId, Record<string, () => Promise<JsonModule>>> = {
  // Literal glob patterns are intentional: Vite discovers and splits every candidate
  // at build time; the catalog only chooses which statically known loader to expose.
  junior: import.meta.glob<JsonModule>('@data/questions/*.json'),
  middle: import.meta.glob<JsonModule>('@data-mid/questions/*.json'),
}

function moduleFor(levelId: ResourceLevelId, questionFile: string) {
  return Object.entries(questionModules[levelId]).find(
    ([path]) => path.endsWith(`/${questionFile}`)
  )?.[1]
}

const examLoaders = Object.fromEntries(
  catalogExams.flatMap((exam) => {
    const loader = moduleFor(exam.levelId, exam.questionFile)
    return loader ? [[exam.routeKey, loader] as const] : []
  })
) as Record<string, () => Promise<JsonModule>>

const cache = new Map<string, Promise<ExamData | undefined>>()

export function loadExamData(examKey: string) {
  const cached = cache.get(examKey)
  if (cached) return cached

  const loader = examLoaders[examKey]
  const promise = loader ? loader().then((module) => module.default as ExamData) : Promise.resolve(undefined)
  cache.set(examKey, promise)
  return promise
}
