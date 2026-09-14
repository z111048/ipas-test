import { Link, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PageHeader, StatePanel } from '../../components/ui'
import { findMeta } from './data'
import type { LearningUnit } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import LearningDataControls from './LearningDataControls'

function Availability({ value }: { value: 'preview' | 'published' }) {
  if (!import.meta.env.DEV || value === 'published') return null
  return <div className="alert-warning mb-4" data-learning-preview>開發預覽：內容仍在審核中，不代表已正式發布。</div>
}

function UnitDetail({ id }: { id: string }) {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index ? findMeta(index, 'units', id) : undefined
  const { item, error, retry } = useLearningItem<LearningUnit>('learning-unit', meta?.path)
  if (index === undefined) return <StatePanel tone="loading" title="載入實務補充">正在讀取版本索引…</StatePanel>
  if (indexError) return <StatePanel tone="error" title="無法載入學習內容" action={<button className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</StatePanel>
  if (!index || !meta) return <StatePanel tone="empty" title="找不到這份實務補充">這份內容尚未進入目前版本。<div className="mt-3"><Link to="/learn" className="btn-secondary">返回實務補充</Link></div></StatePanel>
  if (error) return <StatePanel tone="error" title="內容載入失敗" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!item) return <StatePanel tone="loading" title="載入實務補充">正在讀取單元內容…</StatePanel>
  const unit = item.document
  const guide = unit.guideRefs[0]
  const guideTarget = guide?.anchor ?? guide?.blockIds[0]
  return (
    <div className="page-shell w-full">
      <Availability value={item.availability} />
      <PageHeader eyebrow="實務補充" title={unit.title} description={unit.summary} meta={<span className="pill">約 {unit.estimatedMinutes} 分鐘</span>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {guide && <Link className="btn-secondary" to={`${guide.fallbackRoute}${guideTarget ? `#${encodeURIComponent(guideTarget)}` : ''}`}>返回學習指引原文</Link>}
        {unit.labRefs.map((ref) => <Link key={ref.id} className="btn-secondary" to={`/labs/${ref.id}`}>前往實作 Lab</Link>)}
        {unit.projectRefs.map((ref) => <Link key={ref.id} className="btn-secondary" to={`/projects/${ref.id}`}>查看專題</Link>)}
      </div>
      <section className="surface p-5 sm:p-7">
        <div className="prose prose-slate max-w-none leading-8"><ReactMarkdown remarkPlugins={[remarkGfm]}>{item.bodyMarkdown ?? ''}</ReactMarkdown></div>
      </section>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">學習目標與自我檢查</h2>
        <ol className="space-y-3">
          {unit.objectives.map((objective) => <li key={objective.id}><div className="font-semibold text-primary">{objective.action}</div><div className="text-sm leading-6 text-text-light">條件：{objective.condition}；通過標準：{objective.criterion}</div></li>)}
        </ol>
      </section>
    </div>
  )
}

export default function LearnPage() {
  const { unitId } = useParams<{ unitId: string }>()
  const { index, error, retry } = useLearningIndex()
  if (unitId) return <UnitDetail id={unitId} />
  if (index === undefined) return <StatePanel tone="loading" title="載入實務補充">正在讀取版本索引…</StatePanel>
  if (error) return <StatePanel tone="error" title="無法載入學習內容" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!index) return <StatePanel tone="empty" title="實務補充尚未發布">目前版本沒有可用內容。</StatePanel>
  return <div className="page-shell w-full"><Availability value={index.availability} /><PageHeader eyebrow="從概念到決策" title="實務補充" description="用情境、操作與檢查點，把學習指引的概念帶進真實工作流程。" /><div className="grid gap-4 md:grid-cols-2">{index.units.map((unit) => <Link key={unit.id} to={`/learn/${unit.id}`} className="surface block p-5 no-underline transition hover:border-accent"><h2 className="font-bold text-primary">{unit.title}</h2>{unit.summary && <p className="mt-2 text-sm leading-6 text-text-light">{unit.summary}</p>}</Link>)}</div><LearningDataControls /></div>
}
