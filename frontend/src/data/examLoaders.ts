import type { ExamData } from '../types'

type JsonModule = { default: unknown }

const examLoaders: Record<string, () => Promise<JsonModule>> = {
  // 初級 公告試題
  jr_1141_s1: () => import('@data/questions/mock_jr_1141_s1.json'),
  jr_1141_s2: () => import('@data/questions/mock_jr_1141_s2.json'),
  jr_1151_s1: () => import('@data/questions/mock_jr_1151_s1.json'),
  jr_1151_s2: () => import('@data/questions/mock_jr_1151_s2.json'),
  jr_1152_s1: () => import('@data/questions/mock_jr_1152_s1.json'),
  jr_1152_s2: () => import('@data/questions/mock_jr_1152_s2.json'),
  sample: () => import('@data/questions/sample_exam.json'),
  // 中級 公告試題
  mid_1141_s1: () => import('@data-mid/questions/mock_mid_1141_s1.json'),
  mid_1141_s2: () => import('@data-mid/questions/mock_mid_1141_s2.json'),
  mid_1141_s3: () => import('@data-mid/questions/mock_mid_1141_s3.json'),
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
