import type { ExamReferenceAnswer } from '../types'

// 從 ExamResults.tsx 抽出來共用：概念索引的題目彈窗也要拿同一份參考詳解。
// 兩邊各寫一份的話，114 年考卷那組 legacy 題號對應遲早會有一邊漏掉。
type ExamReferenceModule = { default: unknown }

const asReferenceMap = (module: ExamReferenceModule) => module.default as Record<string, ExamReferenceAnswer>
// 唯一入口是下面的 loadReferenceAnswers()——刻意不 export，避免繞過快取
const referenceLoaders: Record<string, () => Promise<Record<string, ExamReferenceAnswer>>> = {
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

/**
 * 參考詳解按考卷分檔（154–245 KB／份，全部 12 份共 2.3 MB）。
 *
 * 這裡的 cache/pending 兩層不是最佳化，是正確性：原本沒有任何快取，
 * 靠的是 ESM module cache 去重——改成 runtime fetch 之後那層就不存在了，
 * 每開一次結果頁或概念索引彈窗都會重抓一份完整詳解。
 * `pending` 另外處理「同一份同時被兩個元件要」的 in-flight 去重。
 */
const cache = new Map<string, Record<string, ExamReferenceAnswer>>()
const pending = new Map<string, Promise<Record<string, ExamReferenceAnswer> | undefined>>()

export function loadReferenceAnswers(
  examKey: string,
): Promise<Record<string, ExamReferenceAnswer> | undefined> {
  const hit = cache.get(examKey)
  if (hit) return Promise.resolve(hit)

  const inFlight = pending.get(examKey)
  if (inFlight) return inFlight

  const loader = referenceLoaders[examKey]
  if (!loader) return Promise.resolve(undefined)

  const promise = loader()
    .then((references) => {
      cache.set(examKey, references)
      return references
    })
    .finally(() => {
      // 失敗的 promise 不留在 pending，否則一次網路抖動就等於這份詳解永久失效
      pending.delete(examKey)
    })
  pending.set(examKey, promise)
  return promise
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

