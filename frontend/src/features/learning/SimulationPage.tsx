import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChoiceOption, PageHeader, StatePanel } from '../../components/ui'
import LearningState from './LearningState'
import { previewBadge } from './PreviewBadge'
import { findMeta, loadLearningItem, loadQuestion, type MockBlueprint, type QuestionRevision, type ReadyAssembly } from './data'
import { learnerRepository, type StoredAttempt } from './state/repository'
import type { AttemptSnapshot, LearningUnit } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import { useFocusMode } from '../../hooks/useFocusMode'
import { localizeTerms } from './displayTerms'
import { LINK_ROW, READING_PAGE } from './layout'

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
  // 作答進行中進入專注模式：手機隱藏頂欄、桌機收合側欄，交卷或離開即還原。
  useFocusMode(record?.snapshot.status === 'active' && !readOnly)

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
      if (!path) throw new Error('題目資料缺漏，請重新整理頁面')
      const question = await loadQuestion(path)
      if (question.questionKey !== ref.questionKey || question.revision !== ref.revision || question.contentHash !== ref.hash) throw new Error('題目已更新，請重新整理頁面')
      return [ref.questionKey, question] as const
    })).then((rows) => active && setQuestions(new Map(rows))).catch((reason) => active && setQuestionError(reason instanceof Error ? reason.message : String(reason)))
    return () => { active = false }
  }, [assembly, questionPaths])

  useEffect(() => {
    if (!blueprint || !assembly || !questions || !index) return
    if (assembly.blueprintHash !== blueprint.contentHash || assembly.poolRef.releaseId !== index.releaseId) {
      setQuestionError('這份診斷已更新，請重新整理頁面')
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
          if (!optionIds || optionIds.some((id) => !question.options.some((option) => option.optionId === id))) throw new Error('題目選項已更新，請重新整理頁面')
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
      if (!meta) throw new Error('找不到錯題對應的單元')
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

  if (index === undefined) return <LearningState tone="loading" title="載入主題診斷" />
  if (indexError) return <LearningState tone="error" title="無法載入主題診斷" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !blueprintMeta || !assemblyMeta) return <LearningState tone="empty" title="這份主題診斷尚未開放">題目與版本全部核對完成後才會開放作答。</LearningState>
  const loadError = blueprintState.error || assemblyState.error || questionError
  if (loadError) return <LearningState tone="error" title="診斷內容不可用" action={<button type="button" className="btn-secondary" onClick={() => { blueprintState.retry(); assemblyState.retry() }}>重試</button>}>{loadError}</LearningState>
  if (!blueprint || !assembly || !questions) return <LearningState tone="loading" title="載入主題診斷">正在核對題目版本…</LearningState>
  if (!record && storageError) return <LearningState tone="error" title="作答未保存">{storageError}。你仍可閱讀其他內容，請先匯出或清理瀏覽器空間再重試。</LearningState>
  if (!record) return <LearningState tone="loading" title="載入主題診斷">正在準備題目…</LearningState>
  const submitted = record.snapshot.status === 'submitted'
  return <div className={READING_PAGE}>
    <PageHeader
      className="mb-4"
      eyebrow="主題診斷"
      title={localizeTerms(blueprint.title)}
      description={submitted ? '已提交。每題下方附上正確答案與解析，答錯的題目可直接回到對應單元複習。' : '作答會自動保存在這個瀏覽器，重新整理後可接著作答。全部作答後才能提交。'}
      meta={<><span className="pill pill-muted">共 {record.snapshot.items.length} 題 · 限時 {Math.round(blueprint.timeLimitSeconds / 60)} 分鐘</span>{previewBadge(assemblyState.item?.availability)}</>}
    />
    <div className="sticky -top-4 md:-top-6 z-10 mb-4 flex items-center justify-between gap-3 rounded-lg border border-border bg-white/95 px-4 py-2 text-ui shadow-sm backdrop-blur">
      <span className="font-semibold text-primary">{answered} / {record.snapshot.items.length} 已答</span>
      {submitted
        ? <span className="text-text-light">已提交</span>
        : <span className="tabular-nums text-text-light">剩餘 <span className="font-semibold text-primary">{Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}</span></span>}
    </div>
    {storageError && <StatePanel tone="error" title="作答未保存" className="mb-4">{storageError}。請重新載入後再繼續，避免覆蓋其他分頁的作答。</StatePanel>}
    <div className="space-y-4">{record.snapshot.items.map((item, indexNumber) => {
      const question = questions.get(item.questionKey)!
      const correct = item.selectedOptionId === question.correctOptionId
      const unitId = assembly.slotAssignments.find((slot) => slot.question.questionKey === item.questionKey)?.quotaId
      const unit = unitId ? remediation.get(unitId) : undefined
      const guide = unit?.guideRefs[0]
      const guideTarget = guide?.anchor ?? guide?.blockIds[0]
      const locked = submitted || readOnly
      return <article key={`${item.questionKey}:${item.revision}`} data-learning-question={item.questionKey} className="surface p-5">
        <h2 className="text-reading font-semibold leading-8 text-primary">{indexNumber + 1}. {item.promptSnapshot.stem}</h2>
        <fieldset className="mt-3 grid min-w-0 gap-2" disabled={locked}>
          <legend className="sr-only">第 {indexNumber + 1} 題選項</legend>
          {item.promptSnapshot.options.map((option) => {
            const picked = item.selectedOptionId === option.optionId
            const state = submitted ? (option.optionId === question.correctOptionId ? 'correct' : picked ? 'wrong' : 'idle') : undefined
            return <ChoiceOption key={option.optionId} kind="button" letter={option.optionId.replace('opt-', '')} selected={picked} locked={locked} state={state} onSelect={() => select(item.questionKey, option.optionId)}>{option.text}</ChoiceOption>
          })}
        </fieldset>
        {submitted && <div className={`mt-3 rounded-lg border p-4 text-reading leading-8 ${correct ? 'border-correct-line bg-correct-soft' : 'border-wrong-line bg-wrong-soft'}`}>
          <div className={`font-semibold ${correct ? 'text-correct' : 'text-wrong'}`}>{correct ? '答對了' : `正確答案：${question.correctOptionId.replace('opt-', '')}`}</div>
          <p className="text-app-text">{question.explanation}</p>
          {!correct && unitId && <div className={`mt-2 ${LINK_ROW}`}><Link to={`/learn/${unitId}`} className="text-link">閱讀對應單元</Link>{guide && guideTarget && <Link to={`${guide.fallbackRoute}#${encodeURIComponent(guideTarget)}`} className="text-link">回到指引原文</Link>}{unit?.labRefs[0] && <Link to={`/labs/${unit.labRefs[0].id}`} className="text-link">用實作練習鞏固</Link>}</div>}
        </div>}
      </article>
    })}</div>
    {!submitted ? <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
      <button type="button" className="btn-primary w-full sm:w-auto" disabled={readOnly || answered !== record.snapshot.items.length} onClick={submit}>提交診斷</button>
      {!readOnly && answered < record.snapshot.items.length && <p className="text-meta text-text-light">還有 {record.snapshot.items.length - answered} 題未作答。</p>}
    </div> : <StatePanel className="mt-5" title={`得分 ${record.snapshot.result?.score.toFixed(0)} 分`}>答對 {record.snapshot.result?.correctCount} / {record.snapshot.result?.eligibleCount} 題。請用錯題下方連結回到實務補充或實作練習。</StatePanel>}
  </div>
}
