import type { ExamData } from '../types'
import { catalogExams, type ResourceLevelId } from './resourceCatalog'
import { cleanExamQuestion } from '../utils/examText'

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
  // 原始 JSON 不動（詳解 pipeline 以題目內容做指紋），PDF 斷行留下的「中文 空白 中文」
  // 在載入時清掉一次；考試頁、概念彈窗等所有讀這裡的畫面都拿到清過的題幹與選項。
  const promise = loader
    ? loader().then((module) => {
        const exam = module.default as ExamData
        return { ...exam, questions: exam.questions.map(cleanExamQuestion) }
      })
    : Promise.resolve(undefined)
  cache.set(examKey, promise)
  return promise
}
