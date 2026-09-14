import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import { findMeta, loadLearningItem, loadQuestion, type MockBlueprint, type QuestionRevision, type ReadyAssembly } from './data'
import { learnerRepository, type StoredAttempt } from './state/repository'
import type { AttemptSnapshot, LearningUnit } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'

function now() { return new Date().toISOString() }

export default function SimulationPage() {
  const { blueprintId } = useParams<{ blueprintId: string }>()
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const blueprintMeta = index && blueprintId ? findMeta(index, 'blueprints', blueprintId) : undefined
  const assemblyMeta = index && blueprintId ? findMeta(index, 'assemblies', blueprintId) : undefined
  const blueprintState = useLearningItem<MockBlueprint>('mock-blueprint', blueprintMeta?.path)
  const assemblyState = useLearningItem<ReadyAssembly>('assembly-result', assemblyMeta?.path)
  const [questions, setQuestions] = useState<Map<string, QuestionRevision>>()
  const [questionError, setQuestionError] = useState<string>()
  const [record, setRecord] = useState<StoredAttempt>()
  const [storageError, setStorageError] = useState<string>()
  const [readOnly, setReadOnly] = useState(false)
  const [remediation, setRemediation] = useState<Map<string, LearningUnit>>(new Map())
  const [secondsLeft, setSecondsLeft] = useState(0)
  const persistedVersion = useRef(0)
  const writeQueue = useRef<Promise<void>>(Promise.resolve())
  const autoSubmitting = useRef(false)

  const blueprint = blueprintState.item?.document
  const assembly = assemblyState.item?.document
  const questionPaths = assemblyState.item?.questionPaths

  useEffect(() => {
    let active = true
    setQuestions(undefined)
    setQuestionError(undefined)
    if (!assembly || !questionPaths) return
    Promise.all(assembly.selectedQuestionRevisions.map(async (ref) => {
      const path = questionPaths[ref.questionKey]
      if (!path) throw new Error(`題目路徑遺失：${ref.questionKey}`)
      const question = await loadQuestion(path)
      if (question.questionKey !== ref.questionKey || question.revision !== ref.revision || question.contentHash !== ref.hash) throw new Error(`題目版本不一致：${ref.questionKey}`)
      return [ref.questionKey, question] as const
    })).then((rows) => active && setQuestions(new Map(rows))).catch((reason) => active && setQuestionError(reason instanceof Error ? reason.message : String(reason)))
    return () => { active = false }
  }, [assembly, questionPaths])

  useEffect(() => {
    if (!blueprint || !assembly || !questions || !index) return
    if (assembly.blueprintHash !== blueprint.contentHash || assembly.poolRef.releaseId !== index.releaseId) {
      setQuestionError('診斷表單與目前發布版本不一致')
      return
    }
    const attemptId = `attempt-${assembly.formId.slice(5, 29)}`
    learnerRepository.getAttempt(attemptId).then(async (stored) => {
      if (stored) {
        persistedVersion.current = stored.writeVersion
        setRecord(stored)
        return
      }
      const startedAt = now()
      const displayByQuestion = new Map(assembly.displayedOptionIds.map((entry) => [entry.question.questionKey, entry.optionIds]))
      const snapshot: AttemptSnapshot = {
        schemaVersion: 1, attemptId, mode: 'simulation', status: 'active', formId: assembly.formId,
        releaseId: index.releaseId, blueprintHash: assembly.blueprintHash, poolRef: assembly.poolRef, poolHash: assembly.poolHash,
        seed: assembly.seed, algorithmVersion: blueprint.algorithmVersion, startedAt,
        deadlineAt: new Date(Date.parse(startedAt) + blueprint.timeLimitSeconds * 1000).toISOString(), submittedAt: null,
        items: assembly.selectedQuestionRevisions.map((ref, position) => {
          const question = questions.get(ref.questionKey)!
          const optionIds = displayByQuestion.get(ref.questionKey)
          if (!optionIds || optionIds.some((id) => !question.options.some((option) => option.optionId === id))) throw new Error(`選項快照不一致：${ref.questionKey}`)
          return { questionKey: ref.questionKey, revision: ref.revision, contentHash: ref.hash, position,
            promptSnapshot: { stem: question.stem, options: optionIds.map((id) => question.options.find((option) => option.optionId === id)!) },
            assets: [], displayedOptionIds: optionIds, selectedOptionId: null, answeredAt: null }
        }), scoringSnapshot: blueprint.scoring,
      }
      const created = await learnerRepository.saveAttempt(snapshot, 0)
      persistedVersion.current = created.writeVersion
      setRecord(created)
    }).catch((reason) => setStorageError(reason instanceof Error ? reason.message : String(reason)))
  }, [assembly, blueprint, index, questions])

  useEffect(() => {
    if (!record) return
    return learnerRepository.subscribeAttempt(record.attemptId, (writeVersion) => {
      if (writeVersion > persistedVersion.current) {
        setReadOnly(true)
        setStorageError('其他分頁已更新這份作答；此分頁已切換為唯讀，請重新載入')
      }
    })
  }, [record?.attemptId])

  useEffect(() => {
    if (!assembly || !index) return
    let active = true
    const unitIds = [...new Set(assembly.slotAssignments.map((slot) => slot.quotaId))]
    Promise.all(unitIds.map(async (unitId) => {
      const meta = findMeta(index, 'units', unitId)
      if (!meta) throw new Error(`找不到錯題對應單元：${unitId}`)
      return [unitId, (await loadLearningItem<LearningUnit>(meta.path)).document] as const
    })).then((rows) => { if (active) setRemediation(new Map(rows)) })
      .catch((reason) => { if (active) setQuestionError(reason instanceof Error ? reason.message : String(reason)) })
    return () => { active = false }
  }, [assembly, index])

  useEffect(() => {
    const deadline = record?.snapshot.deadlineAt
    if (!deadline || record.snapshot.status !== 'active') return
    const update = () => setSecondsLeft(Math.max(0, Math.ceil((Date.parse(deadline) - Date.now()) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [record])

  const answered = useMemo(() => record?.snapshot.items.filter((item) => item.selectedOptionId).length ?? 0, [record])

  const persist = async (snapshot: AttemptSnapshot, submit = false) => {
    if (!record || readOnly) return
    writeQueue.current = writeQueue.current.then(async () => {
      try {
        const saved = submit
          ? await learnerRepository.submitAttempt(snapshot, persistedVersion.current)
          : await learnerRepository.saveAttempt(snapshot, persistedVersion.current)
        persistedVersion.current = saved.writeVersion
        setRecord((current) => current ? { ...current, writeVersion: saved.writeVersion, snapshotHash: saved.snapshotHash } : saved)
        setStorageError(undefined)
      } catch (reason) {
        setReadOnly(true)
        setStorageError(reason instanceof Error ? reason.message : String(reason))
      }
    })
    await writeQueue.current
  }

  const select = (questionKey: string, optionId: string) => {
    if (!record || readOnly || record.snapshot.status !== 'active') return
    const snapshot = { ...record.snapshot, items: record.snapshot.items.map((item) => item.questionKey === questionKey ? { ...item, selectedOptionId: optionId, answeredAt: now() } : item) }
    setRecord({ ...record, snapshot })
    void persist(snapshot)
  }

  const submit = () => {
    if (!record || readOnly || !questions || record.snapshot.status !== 'active') return
    const correct = record.snapshot.items.filter((item) => item.selectedOptionId === questions.get(item.questionKey)?.correctOptionId).length
    const eligible = record.snapshot.items.length
    const snapshot: AttemptSnapshot = { ...record.snapshot, status: 'submitted', submittedAt: now(), result: {
      score: eligible ? correct / eligible * 100 : 0, eligibleCount: eligible, correctCount: correct,
      invalidatedQuestionKeys: [], answerKeySnapshot: record.snapshot.items.map((item) => ({ questionKey: item.questionKey, revision: item.revision, correctOptionId: questions.get(item.questionKey)!.correctOptionId })),
    } }
    setRecord({ ...record, snapshot })
    void persist(snapshot, true)
  }

  useEffect(() => {
    const snapshot = record?.snapshot
    if (!snapshot?.deadlineAt || snapshot.status !== 'active' || secondsLeft > 0 || Date.now() < Date.parse(snapshot.deadlineAt) || !questions || autoSubmitting.current) return
    autoSubmitting.current = true
    const correct = snapshot.items.filter((item) => item.selectedOptionId === questions.get(item.questionKey)?.correctOptionId).length
    const eligible = snapshot.items.length
    const submitted: AttemptSnapshot = { ...snapshot, status: 'submitted', submittedAt: now(), result: {
      score: eligible ? correct / eligible * 100 : 0, eligibleCount: eligible, correctCount: correct,
      invalidatedQuestionKeys: [], answerKeySnapshot: snapshot.items.map((item) => ({ questionKey: item.questionKey, revision: item.revision, correctOptionId: questions.get(item.questionKey)!.correctOptionId })),
    } }
    setRecord((current) => current ? { ...current, snapshot: submitted } : current)
    void persist(submitted, true)
  }, [record, questions, secondsLeft])

  if (index === undefined) return <StatePanel tone="loading" title="載入主題診斷" />
  if (indexError) return <StatePanel tone="error" title="無法載入診斷" action={<button className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</StatePanel>
  if (!index || !blueprintMeta || !assemblyMeta) return <StatePanel tone="empty" title="目前沒有可驗證的診斷表單">題池、版本與固定組卷結果完整對上後才會開放作答。</StatePanel>
  const loadError = blueprintState.error || assemblyState.error || questionError
  if (loadError) return <StatePanel tone="error" title="診斷內容不可用" action={<button className="btn-secondary" onClick={() => { blueprintState.retry(); assemblyState.retry() }}>重試</button>}>{loadError}</StatePanel>
  if (!blueprint || !assembly || !questions) return <StatePanel tone="loading" title="載入主題診斷">正在核對題目版本與固定組卷結果…</StatePanel>
  if (!record && storageError) return <StatePanel tone="error" title="作答未保存">{storageError}。你仍可閱讀其他內容，請先匯出或清理瀏覽器空間再重試。</StatePanel>
  if (!record) return <StatePanel tone="loading" title="建立作答紀錄">正在建立版本化快照…</StatePanel>
  const submitted = record.snapshot.status === 'submitted'
  return <div className="page-shell w-full">
    {import.meta.env.DEV && assemblyState.item?.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：這份診斷仍在審核中。</div>}
    <PageHeader eyebrow="10 題主題診斷" title={blueprint.title} description="作答會依題目穩定 ID 保存；重新整理後可續答。" meta={<><span className="pill">{answered} / {record.snapshot.items.length} 已答</span>{!submitted && <span className="pill">剩餘 {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}</span>}</>} />
    {storageError && <StatePanel tone="error" title="作答未保存" className="mb-4">{storageError}。請重新載入後再繼續，避免覆蓋其他分頁的作答。</StatePanel>}
    <div className="space-y-4">{record.snapshot.items.map((item, indexNumber) => {
      const question = questions.get(item.questionKey)!
      const correct = item.selectedOptionId === question.correctOptionId
      const unitId = assembly.slotAssignments.find((slot) => slot.question.questionKey === item.questionKey)?.quotaId
      const unit = unitId ? remediation.get(unitId) : undefined
      const guide = unit?.guideRefs[0]
      const guideTarget = guide?.anchor ?? guide?.blockIds[0]
      return <article key={`${item.questionKey}:${item.revision}`} data-learning-question={item.questionKey} className="surface p-5"><h2 className="font-semibold leading-7 text-primary">{indexNumber + 1}. {item.promptSnapshot.stem}</h2><div className="mt-3 grid gap-2">{item.promptSnapshot.options.map((option) => <button key={option.optionId} type="button" disabled={submitted || readOnly} aria-pressed={item.selectedOptionId === option.optionId} onClick={() => select(item.questionKey, option.optionId)} className={`min-h-11 rounded-lg border px-4 py-3 text-left ${item.selectedOptionId === option.optionId ? 'border-accent bg-[#eef7ff]' : 'border-border bg-white hover:border-accent'}`}><span className="mr-2 font-semibold">{option.optionId.replace('opt-', '')}.</span>{option.text}</button>)}</div>{submitted && <div className={`mt-3 rounded-lg p-3 text-sm leading-6 ${correct ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}><div className="font-semibold">{correct ? '答對了' : `正確答案：${question.correctOptionId.replace('opt-', '')}`}</div><p>{question.explanation}</p>{!correct && unitId && <div className="mt-2 flex flex-wrap gap-3"><Link to={`/learn/${unitId}`} className="text-link">閱讀對應單元</Link>{guide && guideTarget && <Link to={`${guide.fallbackRoute}#${encodeURIComponent(guideTarget)}`} className="text-link">回到指引原文</Link>}<Link to="/labs/lab-imbalanced-classification" className="text-link">用 Lab 練習</Link></div>}</div>}</article>
    })}</div>
    {!submitted ? <button className="btn-primary mt-5 w-full sm:w-auto" disabled={readOnly || answered !== record.snapshot.items.length} onClick={submit}>提交診斷</button> : <StatePanel className="mt-5" title={`得分 ${record.snapshot.result?.score.toFixed(0)} 分`}>答對 {record.snapshot.result?.correctCount} / {record.snapshot.result?.eligibleCount} 題。請用錯題下方連結回到補充或 Lab。</StatePanel>}
  </div>
}
