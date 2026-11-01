import { Link } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import LearningState from './LearningState'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import { catalogExams, catalogLevels } from '../../data/resourceCatalog'

interface ExamAnalysis {
  id: string
  releaseId: string
  inventory: Array<{ examKey: string; kind: 'official' | 'sample'; expected: number | null; present: number; labelReviewed: number; answerDisputed: number }>
  publicationCoverage: { exhaustive: boolean; evidenceIds: string[] }
  measures: Array<{ scopeKey: string; topic: { name: string }; population: number; reviewed: number; matched: number; unknown: number; prevalence: number | null; reviewedPrevalence: number | null; lowerBound: number | null; upperBound: number | null }>
  exclusions: Array<{ reason: string; count: number }>
}

function percent(value: number | null) { return value === null ? '未知' : `${(value * 100).toFixed(1)}%` }

function examLabel(examKey: string) {
  const exam = catalogExams.find((row) => row.key === examKey || row.aliases?.includes(examKey))
  if (!exam) return '其他考卷'
  const level = catalogLevels.find((row) => row.id === exam.levelId)?.label ?? ''
  return exam.title.startsWith(level) ? exam.title : `${level}${exam.title}`
}

export default function LearningAnalysisPage() {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index?.analysis[0]
  const { item, error, retry } = useLearningItem<ExamAnalysis>('exam-analysis', meta?.path)
  if (index === undefined) return <LearningState tone="loading" title="精選例題對照" />
  if (indexError) return <LearningState tone="error" title="無法載入精選例題對照" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !meta) return <LearningState tone="empty" title="精選例題對照尚未開放">目前沒有可核對的對照資料。</LearningState>
  if (error) return <LearningState tone="error" title="對照資料載入失敗" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!item) return <LearningState tone="loading" title="精選例題對照" />
  const analysis = item.document
  const present = analysis.inventory.reduce((sum, row) => sum + row.present, 0)
  const reviewed = analysis.inventory.reduce((sum, row) => sum + row.labelReviewed, 0)
  const measureColumns = ['總題數', '已核對', '考到此主題', '尚未核對', '占已核對題比例', '占總題數比例']
  const inventoryColumns = ['類型', '收錄題數', '已核對主題', '答案有爭議']
  const presentLabel = (row: ExamAnalysis['inventory'][number]) => `${row.present}${row.expected === null ? '（總題數未公布）' : ` / ${row.expected}`}`
  return <div className="page-shell w-full">
    {import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：這份對照仍在審核中。</div>}
    <PageHeader className="mb-5" eyebrow="公告試題" title="精選例題對照" description="以下只列出已逐題核對過的例題。尚未核對的題目仍算在總題數裡，不會被當成「沒有考到」。" />
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="surface p-4"><div className="text-meta text-text-light">收錄題數</div><div className="mt-1 text-2xl font-bold text-primary">{present}</div></div>
      <div className="surface p-4"><div className="text-meta text-text-light">已核對主題的題數</div><div className="mt-1 text-2xl font-bold text-primary">{reviewed}</div></div>
      <div className="surface p-4"><div className="text-meta text-text-light">已收齊所有公告試題</div><div className="mt-1 text-lg font-bold text-primary">{analysis.publicationCoverage.exhaustive ? '是' : '否'}</div></div>
    </div>
    <StatePanel className="mt-4" title="如何閱讀">這是 3–5 題的精選例題對照，不是考頻、命中率或趨勢預測。多主題題目也不應把各列相加當作總題數。</StatePanel>
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">5 題原卷對照</h2>
      <div className="space-y-4">{item.sourceExamples?.map((example, position) => (
        <article key={example.question.questionKey} className="rounded-lg border border-border p-4">
          <div className="text-meta font-semibold text-accent">例題 {position + 1} · 原卷第 {example.source.pageNumber} 頁 · {example.relation === 'prerequisite' ? '先備概念' : '單元可解釋'}</div>
          <h3 className="mt-2 text-reading font-semibold leading-7 text-primary">{example.stem}</h3>
          <p className="mt-2 text-body leading-7 text-text-light">{example.reason}</p>
          <div className="mt-2 flex flex-wrap gap-x-5"><Link className="text-link" to={example.source.route}>查看原卷</Link><Link className="text-link" to={`/learn/${example.unitId}`}>閱讀對應單元</Link></div>
        </article>
      ))}</div>
    </section>
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">各主題出現情形</h2>
      <div className="hidden overflow-x-auto md:block">
        <table className="table-soft"><thead><tr><th>主題</th>{measureColumns.map((label) => <th key={label}>{label}</th>)}</tr></thead><tbody>{analysis.measures.map((row) => <tr key={`${row.scopeKey}:${row.topic.name}`}><td>{row.topic.name}</td><td>{row.population}</td><td>{row.reviewed}</td><td>{row.matched}</td><td>{row.unknown}</td><td>{percent(row.reviewedPrevalence)}</td><td>{percent(row.prevalence)}</td></tr>)}</tbody></table>
      </div>
      <ul className="space-y-3 md:hidden">{analysis.measures.map((row) => {
        const values = [row.population, row.reviewed, row.matched, row.unknown, percent(row.reviewedPrevalence), percent(row.prevalence)]
        return <li key={`${row.scopeKey}:${row.topic.name}`} className="rounded-lg border border-border p-4">
          <div className="text-body font-semibold text-primary">{row.topic.name}</div>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2">{measureColumns.map((label, column) => <div key={label}><dt className="text-meta text-text-light">{label}</dt><dd className="text-body font-semibold text-app-text">{values[column]}</dd></div>)}</dl>
        </li>
      })}</ul>
    </section>
    <section className="surface mt-4 p-5">
      <h2 className="section-title mb-3">來源卷別</h2>
      <div className="hidden overflow-x-auto md:block">
        <table className="table-soft"><thead><tr><th>卷別</th>{inventoryColumns.map((label) => <th key={label}>{label}</th>)}</tr></thead><tbody>{analysis.inventory.map((row) => <tr key={row.examKey}><td>{examLabel(row.examKey)}</td><td>{row.kind === 'official' ? '正式題' : '樣題'}</td><td>{presentLabel(row)}</td><td>{row.labelReviewed}</td><td>{row.answerDisputed}</td></tr>)}</tbody></table>
      </div>
      <ul className="space-y-3 md:hidden">{analysis.inventory.map((row) => {
        const values = [row.kind === 'official' ? '正式題' : '樣題', presentLabel(row), row.labelReviewed, row.answerDisputed]
        return <li key={row.examKey} className="rounded-lg border border-border p-4">
          <div className="text-body font-semibold text-primary">{examLabel(row.examKey)}</div>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2">{inventoryColumns.map((label, column) => <div key={label}><dt className="text-meta text-text-light">{label}</dt><dd className="text-body font-semibold text-app-text">{values[column]}</dd></div>)}</dl>
        </li>
      })}</ul>
    </section>
  </div>
}
