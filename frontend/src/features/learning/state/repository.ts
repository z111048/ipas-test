import type { AttemptSnapshot, LearnerProgress } from '../types'

const DATABASE = 'ipas-learning-v1'
const ATTEMPTS = 'attempts'
const PROGRESS = 'progress'
const HASH = /^sha256:[0-9a-f]{64}$/
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/
const QUESTION_KEY = /^q:(junior|middle):[^:]+:[^:]+$/
const OPTION_ID = /^opt-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/

export class LearnerStorageError extends Error {}
export class LearnerConflictError extends LearnerStorageError {}

function storageError(error: DOMException | null) {
  if (error?.name === 'QuotaExceededError') return new LearnerStorageError('瀏覽器儲存空間已滿；請先匯出備份再清理紀錄')
  return new LearnerStorageError(error?.message ?? '瀏覽器儲存失敗')
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(storageError(request.error))
  })
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onabort = transaction.onerror = () => reject(storageError(transaction.error))
  })
}

async function database(): Promise<IDBDatabase> {
  if (!('indexedDB' in window)) throw new LearnerStorageError('此瀏覽器未提供學習紀錄儲存功能')
  const request = indexedDB.open(DATABASE, 1)
  request.onupgradeneeded = () => {
    const db = request.result
    if (!db.objectStoreNames.contains(ATTEMPTS)) db.createObjectStore(ATTEMPTS, { keyPath: 'attemptId' })
    if (!db.objectStoreNames.contains(PROGRESS)) db.createObjectStore(PROGRESS, { keyPath: 'key' })
  }
  return requestResult(request)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function exactRecord(value: unknown, required: string[], optional: string[] = []): Record<string, unknown> {
  if (!isRecord(value)) throw new LearnerStorageError('匯入檔格式不符')
  const allowed = new Set([...required, ...optional])
  if (required.some((key) => !(key in value)) || Object.keys(value).some((key) => !allowed.has(key))) {
    throw new LearnerStorageError('匯入檔含缺漏或未允許欄位')
  }
  return value
}

function text(value: unknown, pattern?: RegExp): string {
  if (typeof value !== 'string' || (pattern && !pattern.test(value))) throw new LearnerStorageError('匯入檔文字欄位格式不符')
  return value
}

function integer(value: unknown, minimum = 0): number {
  if (!Number.isInteger(value) || (value as number) < minimum) throw new LearnerStorageError('匯入檔整數欄位格式不符')
  return value as number
}

function finiteNumber(value: unknown, minimum?: number, maximum?: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || (minimum !== undefined && value < minimum) || (maximum !== undefined && value > maximum)) {
    throw new LearnerStorageError('匯入檔數值欄位格式不符')
  }
  return value
}

function utc(value: unknown, nullable = false): string | null {
  if (nullable && value === null) return null
  const result = text(value)
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(result) || !Number.isFinite(Date.parse(result))) {
    throw new LearnerStorageError('匯入檔日期必須是 UTC')
  }
  return result
}

function canonicalValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalValue)
  if (isRecord(value)) return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalValue(value[key])]))
  return value
}

export async function snapshotHash(snapshot: AttemptSnapshot): Promise<`sha256:${string}`> {
  const bytes = new TextEncoder().encode(JSON.stringify(canonicalValue(snapshot)))
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return `sha256:${Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')}`
}

function validateSnapshot(value: unknown): AttemptSnapshot {
  const row = exactRecord(value,
    ['schemaVersion', 'attemptId', 'mode', 'status', 'formId', 'releaseId', 'blueprintHash', 'poolRef', 'poolHash', 'seed', 'algorithmVersion', 'startedAt', 'deadlineAt', 'submittedAt', 'items', 'scoringSnapshot'], ['result'])
  if (row.schemaVersion !== 1 || !['practice', 'simulation'].includes(String(row.mode)) || !['active', 'submitted', 'abandoned'].includes(String(row.status))) throw new LearnerStorageError('匯入作答版本或狀態不支援')
  text(row.attemptId, IDENTIFIER); text(row.formId, IDENTIFIER); text(row.releaseId, IDENTIFIER); text(row.blueprintHash, HASH); text(row.poolHash, HASH)
  text(row.seed, /^[0-9a-f]{32}$/); text(row.algorithmVersion); utc(row.startedAt); utc(row.deadlineAt, true); utc(row.submittedAt, true)
  const poolRef = exactRecord(row.poolRef, ['id', 'releaseId', 'hash'])
  text(poolRef.id, IDENTIFIER); text(poolRef.releaseId, IDENTIFIER); text(poolRef.hash, HASH)
  if (poolRef.releaseId !== row.releaseId || poolRef.hash !== row.poolHash) throw new LearnerStorageError('匯入作答的版本引用不一致')
  if (!Array.isArray(row.items) || row.items.length < 1) throw new LearnerStorageError('匯入作答沒有題目')
  const identities = new Set<string>()
  row.items.forEach((unknownItem, position) => {
    const item = exactRecord(unknownItem, ['questionKey', 'revision', 'contentHash', 'position', 'promptSnapshot', 'assets', 'displayedOptionIds', 'selectedOptionId', 'answeredAt'], ['contextSnapshot'])
    const key = `${text(item.questionKey, QUESTION_KEY)}:${integer(item.revision, 1)}`
    if (identities.has(key) || item.position !== position) throw new LearnerStorageError('匯入作答的題目順序或版本重複')
    identities.add(key); text(item.contentHash, HASH); utc(item.answeredAt, true)
    if (item.contextSnapshot !== undefined) text(item.contextSnapshot)
    const prompt = exactRecord(item.promptSnapshot, ['stem', 'options'])
    text(prompt.stem)
    if (!Array.isArray(prompt.options) || prompt.options.length < 2) throw new LearnerStorageError('匯入題目選項不足')
    const optionIds = prompt.options.map((unknownOption) => {
      const option = exactRecord(unknownOption, ['optionId', 'text'])
      text(option.text)
      return text(option.optionId, OPTION_ID)
    })
    if (new Set(optionIds).size !== optionIds.length || !Array.isArray(item.displayedOptionIds)
      || item.displayedOptionIds.length !== optionIds.length || item.displayedOptionIds.some((id, index) => id !== optionIds[index])) {
      throw new LearnerStorageError('匯入題目的選項快照不一致')
    }
    if (item.selectedOptionId !== null && !optionIds.includes(text(item.selectedOptionId, OPTION_ID))) throw new LearnerStorageError('匯入答案不在題目選項中')
    if (!Array.isArray(item.assets)) throw new LearnerStorageError('匯入題目資產格式不符')
    item.assets.forEach((unknownAsset) => { const asset = exactRecord(unknownAsset, ['path', 'hash']); text(asset.path); text(asset.hash, HASH) })
  })
  const scoring = exactRecord(row.scoringSnapshot, ['correct', 'incorrect', 'unanswered', 'passingPercent'])
  finiteNumber(scoring.correct); if (scoring.incorrect !== 0 || scoring.unanswered !== 0) throw new LearnerStorageError('匯入計分規則不支援')
  finiteNumber(scoring.passingPercent, 0, 100)
  if (row.result !== undefined) {
    const result = exactRecord(row.result, ['score', 'eligibleCount', 'correctCount', 'invalidatedQuestionKeys', 'answerKeySnapshot'])
    finiteNumber(result.score, 0, 100); integer(result.eligibleCount, 1); integer(result.correctCount)
    if (!Array.isArray(result.invalidatedQuestionKeys) || !Array.isArray(result.answerKeySnapshot)) throw new LearnerStorageError('匯入成績格式不符')
    result.invalidatedQuestionKeys.forEach((key) => text(key, QUESTION_KEY))
    result.answerKeySnapshot.forEach((unknownAnswer) => { const answer = exactRecord(unknownAnswer, ['questionKey', 'revision', 'correctOptionId']); text(answer.questionKey, QUESTION_KEY); integer(answer.revision, 1); text(answer.correctOptionId, OPTION_ID) })
  }
  if (row.status === 'active' && (row.result !== undefined || row.submittedAt !== null)) throw new LearnerStorageError('進行中作答不可含成績或提交時間')
  if (row.status === 'submitted' && (row.result === undefined || row.submittedAt === null)) throw new LearnerStorageError('已提交作答缺少成績或提交時間')
  return row as unknown as AttemptSnapshot
}

function validateProgress(value: unknown): LearnerProgress {
  const row = exactRecord(value, ['schemaVersion', 'target', 'targetHash', 'writeVersion', 'state', 'updatedAt'], ['openedAt', 'selfReportedAt'])
  if (row.schemaVersion !== 1 || !['not_started', 'in_progress', 'self_reported_complete'].includes(String(row.state))) throw new LearnerStorageError('匯入進度版本或狀態不支援')
  const target = exactRecord(row.target, ['kind', 'id', 'revision'])
  if (!['unit', 'project', 'path', 'lab'].includes(String(target.kind))) throw new LearnerStorageError('匯入進度類型不支援')
  text(target.id, IDENTIFIER); integer(target.revision, 1); text(row.targetHash, HASH); integer(row.writeVersion, 1); utc(row.updatedAt)
  if (row.openedAt !== undefined) utc(row.openedAt)
  if (row.selfReportedAt !== undefined) utc(row.selfReportedAt)
  if (row.state === 'self_reported_complete' && row.selfReportedAt === undefined) throw new LearnerStorageError('自評完成紀錄缺少時間')
  return row as unknown as LearnerProgress
}

export interface StoredAttempt {
  attemptId: string
  schemaVersion: 1
  writeVersion: number
  snapshotHash: `sha256:${string}`
  snapshot: AttemptSnapshot
  importedFrom?: string
}
interface StoredProgress extends LearnerProgress { key: string }
export interface ImportPreview { attempts: number; progress: number; raw: string }

function progressKey(progress: LearnerProgress) {
  return `${progress.target.kind}:${progress.target.id}:${progress.target.revision}`
}

async function parseImport(raw: string) {
  if (new Blob([raw]).size > 10 * 1024 * 1024) throw new LearnerStorageError('匯入檔超過 10 MB')
  let parsed: unknown
  try { parsed = JSON.parse(raw) } catch { throw new LearnerStorageError('匯入檔不是有效 JSON') }
  const payload = exactRecord(parsed, ['schemaVersion', 'attempts', 'progress'])
  if (payload.schemaVersion !== 1 || !Array.isArray(payload.attempts) || !Array.isArray(payload.progress)) throw new LearnerStorageError('匯入檔格式不符')
  const attempts = await Promise.all(payload.attempts.map(async (unknownEnvelope) => {
    const envelope = exactRecord(unknownEnvelope, ['schemaVersion', 'writeVersion', 'snapshotHash', 'snapshot'], ['importedFrom'])
    if (envelope.schemaVersion !== 1) throw new LearnerStorageError('匯入作答版本不支援')
    integer(envelope.writeVersion, 1); text(envelope.snapshotHash, HASH)
    if (envelope.importedFrom !== undefined) text(envelope.importedFrom, IDENTIFIER)
    const snapshot = validateSnapshot(envelope.snapshot)
    if (await snapshotHash(snapshot) !== envelope.snapshotHash) throw new LearnerStorageError('匯入作答內容已被修改或 hash 不符')
    return { schemaVersion: 1 as const, writeVersion: envelope.writeVersion as number, snapshotHash: envelope.snapshotHash as `sha256:${string}`, snapshot, importedFrom: envelope.importedFrom as string | undefined }
  }))
  return { attempts, progress: payload.progress.map(validateProgress) }
}

export class LearnerRepository {
  private channel = typeof BroadcastChannel === 'undefined' ? undefined : new BroadcastChannel('ipas-learning-attempts-v1')

  async getAttempt(attemptId: string): Promise<StoredAttempt | undefined> {
    const db = await database()
    const row = await requestResult<StoredAttempt | undefined>(db.transaction(ATTEMPTS).objectStore(ATTEMPTS).get(attemptId))
    if (!row) return undefined
    const snapshot = validateSnapshot(row.snapshot)
    const digest = await snapshotHash(snapshot)
    if (row.schemaVersion === 1 && row.snapshotHash && row.snapshotHash !== digest) {
      throw new LearnerStorageError('本機作答快照已被修改或損壞，拒絕續答')
    }
    return { ...row, schemaVersion: 1, snapshotHash: digest, snapshot }
  }

  async saveAttempt(snapshot: AttemptSnapshot, expectedWriteVersion?: number, importedFrom?: string): Promise<StoredAttempt> {
    validateSnapshot(snapshot)
    const digest = await snapshotHash(snapshot)
    const db = await database()
    const transaction = db.transaction(ATTEMPTS, 'readwrite')
    const store = transaction.objectStore(ATTEMPTS)
    const current = await requestResult<StoredAttempt | undefined>(store.get(snapshot.attemptId))
    if (current?.snapshotHash === digest) {
      await transactionDone(transaction)
      return current
    }
    if (expectedWriteVersion !== undefined && (current?.writeVersion ?? 0) !== expectedWriteVersion) {
      transaction.abort()
      throw new LearnerConflictError('其他分頁已更新這份作答，請重新載入')
    }
    if (!current) {
      const rows = await requestResult<StoredAttempt[]>(store.getAll())
      if (rows.length >= 100) throw new LearnerStorageError('本機已達 100 筆學習作答上限；請先匯出備份並由你選擇清理')
      const projectedBytes = new Blob([JSON.stringify(rows), JSON.stringify(snapshot)]).size
      if (projectedBytes > 50 * 1024 * 1024) throw new LearnerStorageError('本機學習快照已達 50 MB 上限；請先匯出備份並由你選擇清理')
    }
    const record: StoredAttempt = { attemptId: snapshot.attemptId, schemaVersion: 1, writeVersion: (current?.writeVersion ?? 0) + 1, snapshotHash: digest, snapshot, ...(importedFrom ? { importedFrom } : {}) }
    try { store.put(record) } catch (error) { throw storageError(error instanceof DOMException ? error : null) }
    await transactionDone(transaction)
    this.channel?.postMessage({ attemptId: record.attemptId, writeVersion: record.writeVersion })
    return record
  }

  async submitAttempt(snapshot: AttemptSnapshot, expectedWriteVersion?: number) {
    return this.saveAttempt({ ...snapshot, status: 'submitted' }, expectedWriteVersion)
  }

  subscribeAttempt(attemptId: string, listener: (writeVersion: number) => void) {
    if (!this.channel) return () => undefined
    const receive = (event: MessageEvent) => {
      if (isRecord(event.data) && event.data.attemptId === attemptId && Number.isInteger(event.data.writeVersion)) listener(event.data.writeVersion as number)
    }
    this.channel.addEventListener('message', receive)
    return () => this.channel?.removeEventListener('message', receive)
  }

  async listProgress(): Promise<LearnerProgress[]> {
    const db = await database()
    const rows = await requestResult<StoredProgress[]>(db.transaction(PROGRESS).objectStore(PROGRESS).getAll())
    return rows.map(({ key: _key, ...progress }) => progress)
  }

  async upsertProgress(progress: LearnerProgress): Promise<void> {
    validateProgress(progress)
    const db = await database()
    const transaction = db.transaction(PROGRESS, 'readwrite')
    try { transaction.objectStore(PROGRESS).put({ ...progress, key: progressKey(progress) }) } catch (error) { throw storageError(error instanceof DOMException ? error : null) }
    await transactionDone(transaction)
  }

  async exportData(): Promise<string> {
    const db = await database()
    const rows = await requestResult<StoredAttempt[]>(db.transaction(ATTEMPTS).objectStore(ATTEMPTS).getAll())
    const attempts = await Promise.all(rows.map(async ({ attemptId: _key, ...row }) => {
      const digest = await snapshotHash(validateSnapshot(row.snapshot))
      if (row.snapshotHash && row.snapshotHash !== digest) throw new LearnerStorageError('本機作答快照已被修改或損壞，拒絕匯出')
      return { ...row, schemaVersion: 1 as const, snapshotHash: digest }
    }))
    return JSON.stringify({ schemaVersion: 1, attempts, progress: await this.listProgress() })
  }

  async previewImport(raw: string): Promise<ImportPreview> {
    const payload = await parseImport(raw)
    return { attempts: payload.attempts.length, progress: payload.progress.length, raw }
  }

  async importData(raw: string): Promise<void> {
    const payload = await parseImport(raw)
    for (const envelope of payload.attempts) {
      const current = await this.getAttempt(envelope.snapshot.attemptId)
      if (current?.snapshotHash === envelope.snapshotHash) continue
      const { result: _untrustedResult, ...withoutResult } = envelope.snapshot
      const suffix = envelope.snapshotHash.slice(7, 31)
      const attemptId = `imported-${suffix}`
      if (await this.getAttempt(attemptId)) continue
      const historical: AttemptSnapshot = { ...withoutResult, attemptId, status: 'abandoned', submittedAt: null }
      await this.saveAttempt(historical, 0, envelope.snapshot.attemptId)
    }
    const existingProgress = new Set((await this.listProgress()).map(progressKey))
    for (const row of payload.progress) {
      if (existingProgress.has(progressKey(row))) continue
      await this.upsertProgress(row)
    }
  }

  async clearData(): Promise<void> {
    const db = await database()
    const transaction = db.transaction([ATTEMPTS, PROGRESS], 'readwrite')
    transaction.objectStore(ATTEMPTS).clear()
    transaction.objectStore(PROGRESS).clear()
    await transactionDone(transaction)
  }
}

export const learnerRepository = new LearnerRepository()
