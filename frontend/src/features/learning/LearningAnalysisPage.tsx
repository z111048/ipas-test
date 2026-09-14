import { Link } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'

interface ExamAnalysis {
  id: string
  releaseId: string
  inventory: Array<{ examKey: string; kind: 'official' | 'sample'; expected: number | null; present: number; labelReviewed: number; answerDisputed: number }>
  publicationCoverage: { exhaustive: boolean; evidenceIds: string[] }
  measures: Array<{ scopeKey: string; topic: { name: string }; population: number; reviewed: number; matched: number; unknown: number; prevalence: number | null; reviewedPrevalence: number | null; lowerBound: number | null; upperBound: number | null }>
  exclusions: Array<{ reason: string; count: number }>
}

function percent(value: number | null) { return value === null ? '未知' : `${(value * 100).toFixed(1)}%` }

export default function LearningAnalysisPage() {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index?.analysis[0]
  const { item, error, retry } = useLearningItem<ExamAnalysis>('exam-analysis', meta?.path)
  if (index === undefined) return <StatePanel tone="loading" title="載入精選例題對照" />
  if (indexError) return <StatePanel tone="error" title="無法載入資料" action={<button className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</StatePanel>
  if (!index || !meta) return <StatePanel tone="empty" title="精選例題對照尚未發布">目前版本沒有可核對的分析資料。</StatePanel>
  if (error) return <StatePanel tone="error" title="分析載入失敗" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!item) return <StatePanel tone="loading" title="載入精選例題對照" />
  const analysis = item.document
  const present = analysis.inventory.reduce((sum, row) => sum + row.present, 0)
  const reviewed = analysis.inventory.reduce((sum, row) => sum + row.labelReviewed, 0)
  return <div className="page-shell w-full">
    {import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：這份對照仍在審核中。</div>}
    <PageHeader eyebrow="範圍透明的策展子集" title="精選例題對照" description="以下只說明已逐題核對的例題。未審題保留在分母，不會被當成沒有考到。" />
    <div className="grid gap-3 sm:grid-cols-3"><div className="surface p-4"><div className="text-xs text-text-light">收錄母體</div><div className="mt-1 text-2xl font-bold text-primary">{present}</div></div><div className="surface p-4"><div className="text-xs text-text-light">已審例題</div><div className="mt-1 text-2xl font-bold text-primary">{reviewed}</div></div><div className="surface p-4"><div className="text-xs text-text-light">完整覆蓋</div><div className="mt-1 text-lg font-bold text-primary">{analysis.publicationCoverage.exhaustive ? '是' : '否'}</div></div></div>
    <StatePanel className="mt-4" title="如何閱讀">這是 3–5 題的精選例題對照，不是考頻、命中率或趨勢預測。多主題題目也不應把各列相加當作總題數。</StatePanel>
    <section className="surface mt-4 p-5"><h2 className="section-title mb-3">5 題原卷對照</h2><div className="space-y-4">{item.sourceExamples?.map((example, index) => <article key={example.question.questionKey} className="rounded-lg border border-border p-4"><div className="text-xs font-semibold text-accent">例題 {index + 1} · 原卷第 {example.source.pageNumber} 頁 · {example.relation === 'prerequisite' ? '先備概念' : '單元可解釋'}</div><h3 className="mt-2 font-semibold leading-7 text-primary">{example.stem}</h3><p className="mt-2 text-sm leading-6 text-text-light">{example.reason}</p><div className="mt-3 flex flex-wrap gap-3"><Link className="text-link" to={example.source.route}>查看原卷</Link><Link className="text-link" to={`/learn/${example.unitId}`}>閱讀對應單元</Link></div></article>)}</div></section>
    <section className="surface mt-4 overflow-x-auto p-5"><h2 className="section-title mb-3">主題標註範圍</h2><table className="table-soft"><thead><tr><th>主題</th><th>母體</th><th>已審</th><th>符合</th><th>未知</th><th>已審子集比例</th><th>完整母體比例</th></tr></thead><tbody>{analysis.measures.map((row) => <tr key={`${row.scopeKey}:${row.topic.name}`}><td>{row.topic.name}</td><td>{row.population}</td><td>{row.reviewed}</td><td>{row.matched}</td><td>{row.unknown}</td><td>{percent(row.reviewedPrevalence)}</td><td>{percent(row.prevalence)}</td></tr>)}</tbody></table></section>
    <section className="surface mt-4 overflow-x-auto p-5"><h2 className="section-title mb-3">來源卷別</h2><table className="table-soft"><thead><tr><th>卷別</th><th>類型</th><th>收錄</th><th>已審標註</th><th>答案爭議</th></tr></thead><tbody>{analysis.inventory.map((row) => <tr key={row.examKey}><td>{row.examKey}</td><td>{row.kind === 'official' ? '正式題' : '樣題'}</td><td>{row.present}{row.expected === null ? '（預期未知）' : ` / ${row.expected}`}</td><td>{row.labelReviewed}</td><td>{row.answerDisputed}</td></tr>)}</tbody></table></section>
  </div>
}
