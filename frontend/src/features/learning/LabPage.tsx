import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import LearningState from './LearningState'
import { findMeta, learningAssetUrl } from './data'
import { localizeTerms } from './displayTerms'
import { ACTION_ROW, READING_PAGE, formatMinutes } from './layout'
import { learnerRepository } from './state/repository'
import type { Lab, LabPhase, LearnerProgress } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'

function utcNow() { return new Date().toISOString() }

const PHASE_LABELS: Record<LabPhase, string> = {
  setup: '環境準備',
  worked: '範例示範',
  guided: '引導練習',
  independent: '獨立實作',
  check: '自我檢查',
  reflection: '反思與限制',
}

function formatSeconds(seconds: number) {
  return seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} 分鐘` : `${seconds} 秒`
}

function formatMemory(megabytes: number) {
  return megabytes >= 1024 && megabytes % 1024 === 0 ? `${megabytes / 1024} GB` : `${megabytes} MB`
}

export default function LabPage() {
  const { labId } = useParams<{ labId: string }>()
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index && labId ? findMeta(index, 'labs', labId) : undefined
  const { item, error, retry } = useLearningItem<Lab>('lab', meta?.path)
  const [progress, setProgress] = useState<LearnerProgress>()
  const [storageError, setStorageError] = useState<string>()
  const [assetError, setAssetError] = useState<string>()

  useEffect(() => {
    if (!item) return
    learnerRepository.listProgress()
      .then((rows) => setProgress(rows.find((row) => row.target.kind === 'lab' && row.target.id === item.document.id && row.target.revision === item.document.revision)))
      .catch((reason) => setStorageError(reason instanceof Error ? reason.message : String(reason)))
  }, [item])

  const backToProjects = <Link to="/projects" className="btn-secondary">返回實務專題</Link>
  if (!labId) return <LearningState tone="empty" title="找不到這份實作練習" action={backToProjects}>網址不完整，請從實務專題重新進入。</LearningState>
  if (index === undefined) return <LearningState tone="loading" title="載入實作練習" />
  if (indexError) return <LearningState tone="error" title="無法載入實作練習" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !meta) return <LearningState tone="empty" title="找不到這份實作練習" action={backToProjects}>這份實作練習尚未開放，或網址已經變更。</LearningState>
  if (error) return <LearningState tone="error" title="實作練習載入失敗" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!item) return <LearningState tone="loading" title="載入實作練習" />

  const lab = item.document
  const saveProgress = async (state: LearnerProgress['state'], opened = false) => {
    const now = utcNow()
    const next: LearnerProgress = {
      schemaVersion: 1,
      target: { kind: 'lab', id: lab.id, revision: lab.revision },
      targetHash: lab.contentHash,
      writeVersion: (progress?.writeVersion ?? 0) + 1,
      state,
      openedAt: opened ? progress?.openedAt ?? now : progress?.openedAt,
      selfReportedAt: state === 'self_reported_complete' ? now : progress?.selfReportedAt,
      updatedAt: now,
    }
    try {
      await learnerRepository.upsertProgress(next)
      setProgress(next)
      setStorageError(undefined)
    } catch (reason) {
      setStorageError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  const download = async (path: string, filename: string) => {
    try {
      const url = await learningAssetUrl(path)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      anchor.click()
      setAssetError(undefined)
    } catch (reason) {
      setAssetError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  const terms = new Set<string>()
  const totalMinutes = lab.steps.reduce((sum, step) => sum + step.estimatedMinutes, 0)
  const status = progress?.state === 'self_reported_complete' ? '已自評完成' : progress?.openedAt ? '已開啟，尚未自評完成' : '尚未開始'
  const facts: Array<[string, string]> = [
    ['Python 版本', lab.environment.pythonVersion],
    ['運算資源', `${lab.executionPolicy.cpuOnly ? '只用 CPU' : 'CPU／GPU'}，記憶體上限 ${formatMemory(lab.executionPolicy.maxMemoryMb)}`],
    ['執行時間上限', `整份 ${formatSeconds(lab.executionPolicy.totalTimeoutSeconds)}，單一儲存格 ${formatSeconds(lab.executionPolicy.cellTimeoutSeconds)}`],
    ['網路', lab.executionPolicy.networkPolicy === 'offline' ? '執行時離線' : '只連核准的資源'],
    ['資料集', `${lab.datasets.length} 份固定版本`],
  ]
  return <div className={READING_PAGE}>
    {import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：實作練習仍在審核，執行結果不代表平台認證。</div>}
    <PageHeader
      className="mb-5"
      eyebrow="實作練習"
      title={localizeTerms(lab.title)}
      description="先下載 Starter 練習檔，在自己的 Colab 工作階段手動上傳並執行。"
      meta={<>{totalMinutes > 0 && <span className="pill">{formatMinutes(totalMinutes)}</span>}<span className="pill pill-muted">{lab.steps.length} 個步驟</span></>}
      actions={backToProjects}
    />
    {storageError && <StatePanel tone="error" title="學習紀錄未保存" className="mb-4">{storageError}。你仍可繼續閱讀與下載。</StatePanel>}
    {assetError && <StatePanel tone="error" title="下載失敗" className="mb-4">{assetError}</StatePanel>}
    <section className="surface p-5">
      <h2 className="section-title mb-3">開始實作</h2>
      <div className={ACTION_ROW}>
        {item.assetLocations?.map((asset) => <button type="button" key={asset.variant} className={asset.variant === 'starter' ? 'btn-primary' : 'btn-secondary'} onClick={() => download(asset.path, `${lab.id}-${asset.variant}.ipynb`)}>{asset.variant === 'starter' ? '下載 Starter 練習檔' : '下載 Solution 參考解答'}（{Math.ceil(asset.size / 1024)} KB）</button>)}
        <a className="btn-secondary" href="https://colab.research.google.com/#create=true" target="_blank" rel="noreferrer" onClick={() => void saveProgress('in_progress', true)}>開啟 Colab 並手動上傳</a>
      </div>
      {(item.supportAssets?.length ?? 0) > 0 && <>
        <h3 className="mt-5 mb-2 text-meta font-semibold text-text-light">練習用資料與設定檔</h3>
        <div className={ACTION_ROW}>
          {item.supportAssets?.map((asset) => {
            const parts = asset.path.split('/')
            return <button type="button" key={asset.path} className="btn-secondary" onClick={() => download(asset.path, parts[parts.length - 1] ?? asset.label)}>{asset.label}（{Math.ceil(asset.size / 1024)} KB）</button>
          })}
        </div>
      </>}
      <p className="mt-3 text-body leading-7 text-text-light">開啟或下載不等於完成。練習檔需由你執行、修改並依檢查點核對；參考解答請在自己完成後再對照。</p>
    </section>
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">步驟與檢查</h2>
      <ol className="space-y-3">{lab.steps.map((step, position) => (
        <li key={step.id} className="border-l-4 border-accent pl-4">
          <div className="text-reading font-semibold text-primary">{position + 1}. {PHASE_LABELS[step.phase] ?? '練習步驟'}</div>
          <div className="text-ui leading-6 text-text-light">約 {step.estimatedMinutes} 分鐘 · {step.expectedArtifacts.length ? `產出 ${step.expectedArtifacts.join('、')}` : '依筆記本提示完成'}</div>
        </li>
      ))}</ol>
    </section>
    {lab.reflectionPrompts.length > 0 && <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">完成後想一想</h2>
      <ul className="list-disc space-y-2 pl-5 text-body leading-7">{lab.reflectionPrompts.map((prompt) => <li key={prompt}>{localizeTerms(prompt, terms)}</li>)}</ul>
    </section>}
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">環境與資料</h2>
      <dl className="grid gap-3 text-body sm:grid-cols-2">{facts.map(([label, value]) => <div key={label}><dt className="text-meta text-text-light">{label}</dt><dd className="font-semibold">{value}</dd></div>)}</dl>
    </section>
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-2">完成狀態</h2>
      <p className="text-body leading-7 text-text-light">目前：{status}</p>
      <div className={`mt-3 ${ACTION_ROW}`}><button type="button" className="btn-primary" onClick={() => void saveProgress('self_reported_complete')}>我已自行完成並核對</button></div>
      <p className="mt-2 text-meta text-text-light">這是你的自評紀錄，不是系統驗證或考試成績。</p>
    </section>
  </div>
}
