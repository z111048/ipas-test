import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import { findMeta, learningAssetUrl } from './data'
import { learnerRepository } from './state/repository'
import type { Lab, LearnerProgress } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'

function utcNow() { return new Date().toISOString() }

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

  if (!labId) return <StatePanel tone="empty" title="缺少 Lab ID" />
  if (index === undefined) return <StatePanel tone="loading" title="載入 Lab" />
  if (indexError) return <StatePanel tone="error" title="無法載入 Lab" action={<button className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</StatePanel>
  if (!index || !meta) return <StatePanel tone="empty" title="找不到 Lab">這份 Lab 尚未進入目前版本。</StatePanel>
  if (error) return <StatePanel tone="error" title="Lab 載入失敗" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!item) return <StatePanel tone="loading" title="載入 Lab" />

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

  return <div className="page-shell w-full">
    {import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：Lab 仍在審核，執行結果不代表平台認證。</div>}
    <PageHeader eyebrow="實作 Lab" title={lab.title} description="先下載 Starter，在自己的 Colab 工作階段手動上傳並執行。" meta={<span className="pill">CPU · 約 {lab.executionPolicy.totalTimeoutSeconds / 60} 分鐘內</span>} />
    {storageError && <StatePanel tone="error" title="學習紀錄未保存" className="mb-4">{storageError}。你仍可繼續閱讀與下載。</StatePanel>}
    {assetError && <StatePanel tone="error" title="下載失敗" className="mb-4">{assetError}</StatePanel>}
    <section className="surface p-5">
      <h2 className="section-title mb-3">開始實作</h2>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {item.assetLocations?.map((asset) => <button key={asset.variant} className={asset.variant === 'starter' ? 'btn-primary' : 'btn-secondary'} onClick={() => download(asset.path, `${lab.id}-${asset.variant}.ipynb`)}>下載 {asset.variant === 'starter' ? 'Starter' : 'Solution'}（{Math.ceil(asset.size / 1024)} KB）</button>)}
        {item.supportAssets?.map((asset) => {
          const parts = asset.path.split('/')
          return <button key={asset.path} className="btn-secondary" onClick={() => download(asset.path, parts[parts.length - 1] ?? asset.label)}>{asset.label}（{Math.ceil(asset.size / 1024)} KB）</button>
        })}
        <a className="btn-secondary" href="https://colab.research.google.com/#create=true" target="_blank" rel="noreferrer" onClick={() => void saveProgress('in_progress', true)}>開啟 Colab 並手動上傳</a>
      </div>
      <p className="mt-3 text-sm leading-6 text-text-light">開啟或下載不等於完成。Starter 需由你執行、修改並依檢查點核對。</p>
    </section>
    <section className="surface mt-4 p-5"><h2 className="section-title mb-3">環境與資料</h2><dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-text-light">Python</dt><dd className="font-semibold">{lab.environment.pythonVersion}</dd></div><div><dt className="text-text-light">執行環境</dt><dd className="font-semibold">{lab.environment.runtimeProfile}</dd></div><div><dt className="text-text-light">網路策略</dt><dd className="font-semibold">{lab.executionPolicy.networkPolicy === 'offline' ? '執行時離線' : '限核准資源'}</dd></div><div><dt className="text-text-light">資料集</dt><dd className="font-semibold">{lab.datasets.length} 份固定版本</dd></div></dl></section>
    <section className="surface mt-4 p-5"><h2 className="section-title mb-3">步驟與檢查</h2><ol className="space-y-3">{lab.steps.map((step, index) => <li key={step.id} className="border-l-4 border-accent pl-4"><div className="font-semibold text-primary">{index + 1}. {step.phase}</div><div className="text-sm text-text-light">約 {step.estimatedMinutes} 分鐘 · {step.expectedArtifacts.join('、') || '依 notebook 提示完成'}</div></li>)}</ol></section>
    <section className="surface mt-4 p-5"><h2 className="section-title mb-2">完成狀態</h2><p className="text-sm leading-6 text-text-light">目前：{progress?.state === 'self_reported_complete' ? '已自評完成' : progress?.openedAt ? '已開啟，尚未自評完成' : '尚未開始'}</p><button className="btn-primary mt-3" onClick={() => void saveProgress('self_reported_complete')}>我已自行完成並核對</button><p className="mt-2 text-xs text-text-light">這是你的自評紀錄，不是系統驗證或考試成績。</p></section>
    <div className="mt-4"><Link className="text-link" to="/projects">返回專題</Link></div>
  </div>
}
