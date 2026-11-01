import { Link, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PageHeader } from '../../components/ui'
import { findMeta } from './data'
import { localizeTerms, remarkLearningTerms } from './displayTerms'
import { ACTION_ROW, READING_MEASURE, READING_PAGE, formatMinutes } from './layout'
import type { LearningUnit } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import LearningDataControls from './LearningDataControls'
import LearningState from './LearningState'
import { previewBadge } from './PreviewBadge'

function UnitDetail({ id }: { id: string }) {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index ? findMeta(index, 'units', id) : undefined
  const { item, error, retry } = useLearningItem<LearningUnit>('learning-unit', meta?.path)
  if (index === undefined) return <LearningState tone="loading" title="載入實務補充">正在讀取內容…</LearningState>
  if (indexError) return <LearningState tone="error" title="無法載入學習內容" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !meta) return <LearningState tone="empty" title="找不到這份實務補充" action={<Link to="/learn" className="btn-secondary">返回實務補充</Link>}>這份內容尚未開放，或網址已經變更。</LearningState>
  if (error) return <LearningState tone="error" title="內容載入失敗" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!item) return <LearningState tone="loading" title="載入實務補充">正在讀取單元內容…</LearningState>
  const unit = item.document
  const guide = unit.guideRefs[0]
  const guideTarget = guide?.anchor ?? guide?.blockIds[0]
  const terms = new Set<string>()
  const hasNextSteps = unit.labRefs.length > 0 || unit.projectRefs.length > 0
  return (
    <div className={READING_PAGE}>
      <PageHeader
        className="mb-5"
        eyebrow="實務補充"
        title={localizeTerms(unit.title)}
        description={localizeTerms(unit.summary, terms)}
        meta={<><span className="pill">{formatMinutes(unit.estimatedMinutes)}</span>{previewBadge(item.availability)}</>}
        actions={guide && <Link className="btn-secondary" to={`${guide.fallbackRoute}${guideTarget ? `#${encodeURIComponent(guideTarget)}` : ''}`}>返回學習指引原文</Link>}
      />
      <article className="surface p-5 sm:p-7">
        <div className="prose prose-slate max-w-none text-reading leading-8"><ReactMarkdown remarkPlugins={[remarkGfm, remarkLearningTerms]}>{item.bodyMarkdown ?? ''}</ReactMarkdown></div>
      </article>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">學習目標與自我檢查</h2>
        <ol className="space-y-3">
          {unit.objectives.map((objective) => (
            <li key={objective.id}>
              <div className="text-reading font-semibold text-primary">{localizeTerms(objective.action, terms)}</div>
              <div className="text-ui leading-6 text-text-light">條件：{localizeTerms(objective.condition, terms)}；通過標準：{localizeTerms(objective.criterion, terms)}</div>
            </li>
          ))}
        </ol>
      </section>
      {hasNextSteps && (
        <section className="surface mt-4 p-5" aria-labelledby="unit-next-steps">
          <h2 id="unit-next-steps" className="section-title mb-3">下一步</h2>
          <div className={ACTION_ROW}>
            {unit.labRefs.map((ref) => <Link key={ref.id} className="btn-primary" to={`/labs/${ref.id}`}>前往實作練習</Link>)}
            {unit.projectRefs.map((ref) => <Link key={ref.id} className="btn-secondary" to={`/projects/${ref.id}`}>查看實務專題</Link>)}
          </div>
        </section>
      )}
    </div>
  )
}

export default function LearnPage() {
  const { unitId } = useParams<{ unitId: string }>()
  const { index, error, retry } = useLearningIndex()
  if (unitId) return <UnitDetail id={unitId} />
  if (index === undefined) return <LearningState tone="loading" title="實務補充">正在讀取內容…</LearningState>
  if (error) return <LearningState tone="error" title="無法載入實務補充" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!index) return <LearningState tone="empty" title="實務補充尚未開放">目前沒有可閱讀的內容。</LearningState>
  return (
    <div className="page-shell w-full">
      <PageHeader className="mb-5" eyebrow="從概念到決策" title="實務補充" description="用情境、操作與檢查點，把學習指引的概念帶進真實工作流程。" meta={previewBadge(index.availability)} />
      <div className="grid gap-4 md:grid-cols-2">
        {index.units.map((unit) => (
          <Link key={unit.id} to={`/learn/${unit.id}`} className="surface block p-5 no-underline transition hover:border-accent">
            <h2 className="text-reading font-bold text-primary">{localizeTerms(unit.title)}</h2>
            {unit.summary && <p className={`mt-2 text-ui leading-6 text-text-light ${READING_MEASURE}`}>{localizeTerms(unit.summary)}</p>}
          </Link>
        ))}
      </div>
      <LearningDataControls />
    </div>
  )
}
