import { Link } from 'react-router-dom'
import { PageHeader } from '../../components/ui'
import LearningState from './LearningState'
import { previewBadge } from './PreviewBadge'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import { localizeTerms } from './displayTerms'
import { LINK_ROW, READING_MEASURE } from './layout'
import { cleanExamText } from '../../utils/examText'

export default function LearningAnalysisPage() {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index?.analysis[0]
  const { item, error, retry } = useLearningItem<Record<string, unknown>>('exam-analysis', meta?.path)
  if (index === undefined) return <LearningState tone="loading" title="精選例題對照" />
  if (indexError) return <LearningState tone="error" title="無法載入精選例題對照" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !meta) return <LearningState tone="empty" title="精選例題對照尚未開放">目前沒有可核對的對照資料。</LearningState>
  if (error) return <LearningState tone="error" title="對照資料載入失敗" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!item) return <LearningState tone="loading" title="精選例題對照" />
  const diagnostic = index.blueprints[0]
  return <div className="page-shell w-full">
    <PageHeader
      className="mb-5"
      title="精選例題對照"
      description="精選幾題公告試題，對照它們考的主題與學習指引出處。這是例題對照，不是考頻或命中率預測。"
      meta={previewBadge(item.availability)}
      actions={diagnostic && <Link className="btn-secondary" to={`/simulations/${diagnostic.id}`}>做一次主題診斷</Link>}
    />
    <section className="surface p-5">
      <h2 className="section-title mb-3">5 題原卷對照</h2>
      <div className="space-y-4">{item.sourceExamples?.map((example, position) => (
        <article key={example.question.questionKey} className="rounded-lg border border-border p-4">
          <div className="text-meta font-semibold text-accent">例題 {position + 1} · 原卷第 {example.source.pageNumber} 頁 · {example.relation === 'prerequisite' ? '先備概念' : '單元可解釋'}</div>
          <h3 data-exam-text className={`mt-2 text-reading font-semibold leading-7 text-primary ${READING_MEASURE}`}>{cleanExamText(example.stem)}</h3>
          <p className={`mt-2 text-body leading-7 text-text-light ${READING_MEASURE}`}>{localizeTerms(example.reason)}</p>
          <div className={`mt-2 ${LINK_ROW}`}><Link className="text-link" to={example.source.route}>查看原卷</Link><Link className="text-link" to={`/learn/${example.unitId}`}>閱讀對應單元</Link></div>
        </article>
      ))}</div>
    </section>
  </div>
}
