import type { ExamReferenceAnswer } from '../types'

// 從 ExamResults.tsx 抽出來共用：概念索引的題目彈窗也要拿同一份參考詳解。
// 兩邊各寫一份的話，114 年考卷那組 legacy 題號對應遲早會有一邊漏掉。
type ExamReferenceModule = { default: unknown }

export const asReferenceMap = (module: ExamReferenceModule) => module.default as Record<string, ExamReferenceAnswer>
export const referenceLoaders: Record<string, () => Promise<Record<string, ExamReferenceAnswer>>> = {
  // 初級
  jr_1141_s1: () => import('../generated/examReferenceAnswers/jr_1141_s1.json').then(asReferenceMap),
  jr_1141_s2: () => import('../generated/examReferenceAnswers/jr_1141_s2.json').then(asReferenceMap),
  jr_1151_s1: () => import('../generated/examReferenceAnswers/jr_1151_s1.json').then(asReferenceMap),
  jr_1151_s2: () => import('../generated/examReferenceAnswers/jr_1151_s2.json').then(asReferenceMap),
  jr_1152_s1: () => import('../generated/examReferenceAnswers/jr_1152_s1.json').then(asReferenceMap),
  jr_1152_s2: () => import('../generated/examReferenceAnswers/jr_1152_s2.json').then(asReferenceMap),
  sample: () => import('../generated/examReferenceAnswers/sample.json').then(asReferenceMap),
  // 中級
  mid_1141_s1: () => import('../generated/examReferenceAnswers/mid_1141_s1.json').then(asReferenceMap),
  mid_1141_s2: () => import('../generated/examReferenceAnswers/mid_1141_s2.json').then(asReferenceMap),
  mid_1141_s3: () => import('../generated/examReferenceAnswers/mid_1141_s3.json').then(asReferenceMap),
  midSample: () => import('../generated/examReferenceAnswers/midSample.json').then(asReferenceMap),
}

const legacyReferencePrefixByExam: Record<string, string> = {
  jr_1141_s1: 'exam1',
  jr_1141_s2: 'exam2',
  mid_1141_s1: 'exam1',
  mid_1141_s2: 'exam2',
  mid_1141_s3: 'exam3',
}

function questionNumberToken(questionId: string) {
  return questionId.match(/_q(\d+)$/)?.[1]
}

export function referenceForQuestion(
  references: Record<string, ExamReferenceAnswer>,
  examKey: string,
  questionId: string,
) {
  const direct = references[questionId]
  if (direct) return direct

  const number = questionNumberToken(questionId)
  if (!number) return undefined

  const legacyPrefix = legacyReferencePrefixByExam[examKey]
  if (legacyPrefix) {
    const legacy = references[`${legacyPrefix}_q${number}`]
    if (legacy) return legacy
  }

  const suffix = `_q${number}`
  const fallbackKeys = Object.keys(references).filter((key) => key.endsWith(suffix))
  if (fallbackKeys.length === 1) return references[fallbackKeys[0]]
  return undefined
}

