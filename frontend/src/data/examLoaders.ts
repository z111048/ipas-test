import type { ExamData } from '../types'

type JsonModule = { default: unknown }

const examLoaders: Record<string, () => Promise<JsonModule>> = {
  mock1: () => import('@data/questions/mock_exam1.json'),
  mock2: () => import('@data/questions/mock_exam2.json'),
  sample: () => import('@data/questions/sample_exam.json'),
  mid1: () => import('@data-mid/questions/mock_exam1.json'),
  mid2: () => import('@data-mid/questions/mock_exam2.json'),
  mid3: () => import('@data-mid/questions/mock_exam3.json'),
  midSample: () => import('@data-mid/questions/sample_exam.json'),
}

const cache = new Map<string, Promise<ExamData | undefined>>()

export function loadExamData(examKey: string) {
  const cached = cache.get(examKey)
  if (cached) return cached

  const loader = examLoaders[examKey]
  const promise = loader ? loader().then((module) => module.default as ExamData) : Promise.resolve(undefined)
  cache.set(examKey, promise)
  return promise
}
