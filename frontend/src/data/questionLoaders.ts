import type { SubjectQuestions } from '../types'

type JsonModule = { default: unknown }

const aiQuestionLoaders: Record<string, () => Promise<JsonModule>> = {
  s1: () => import('@data/questions/subject1_questions.json'),
  s2: () => import('@data/questions/subject2_questions.json'),
  'mid-s1': () => import('@data-mid/questions/subject1_questions.json'),
  'mid-s2': () => import('@data-mid/questions/subject2_questions.json'),
  'mid-s3': () => import('@data-mid/questions/subject3_questions.json'),
}

const guideExerciseLoaders: Record<string, () => Promise<JsonModule>> = {
  s1: () => import('@data/questions/subject1_guide_exercises.json'),
  s2: () => import('@data/questions/subject2_guide_exercises.json'),
  'mid-s1': () => import('@data-mid/questions/subject1_guide_exercises.json'),
  'mid-s2': () => import('@data-mid/questions/subject2_guide_exercises.json'),
  'mid-s3': () => import('@data-mid/questions/subject3_guide_exercises.json'),
}

const cache = new Map<string, Promise<SubjectQuestions | undefined>>()

function loaderFor(subjectId: string, practiceSet?: string) {
  if (practiceSet === 'guide') return guideExerciseLoaders[subjectId]
  return aiQuestionLoaders[subjectId]
}

export function loadSubjectQuestions(subjectId: string, practiceSet?: string) {
  const key = `${subjectId}:${practiceSet ?? 'ai'}`
  const cached = cache.get(key)
  if (cached) return cached

  const loader = loaderFor(subjectId, practiceSet)
  const promise = loader ? loader().then((module) => module.default as SubjectQuestions) : Promise.resolve(undefined)
  cache.set(key, promise)
  return promise
}
