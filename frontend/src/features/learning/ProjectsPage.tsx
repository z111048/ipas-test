import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '../../components/ui'
import { findMeta } from './data'
import type { Project } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import LearningState from './LearningState'

function ProjectDetail({ id }: { id: string }) {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index ? findMeta(index, 'projects', id) : undefined
  const { item, error, retry } = useLearningItem<Project>('project', meta?.path)
  if (index === undefined) return <LearningState tone="loading" title="載入實務專題" />
  if (indexError) return <LearningState tone="error" title="無法載入實務專題" action={<button type="button" className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</LearningState>
  if (!index || !meta) return <LearningState tone="empty" title="找不到這份實務專題" action={<Link to="/projects" className="btn-secondary">返回實務專題</Link>}>這份專題尚未開放，或網址已經變更。</LearningState>
  if (error) return <LearningState tone="error" title="專題載入失敗" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!item) return <LearningState tone="loading" title="載入實務專題" />
  const project = item.document
  return (
    <div className="page-shell w-full">
      {import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：此專題尚未正式發布。</div>}
      <PageHeader className="mb-5" eyebrow="實務專題" title={project.title} description={project.brief.scenario} />
      <section className="surface p-5">
        <h2 className="section-title mb-2">要解決的問題</h2>
        <p className="text-reading leading-7">{project.brief.problemStatement}</p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {project.unitRefs.map((ref) => <Link className="btn-secondary" key={ref.id} to={`/learn/${ref.id}`}>先學：{findMeta(index, 'units', ref.id)?.title ?? '相關單元'}</Link>)}
          {project.labRefs.map((ref) => <Link className="btn-secondary" key={ref.id} to={`/labs/${ref.id}`}>實作：{findMeta(index, 'labs', ref.id)?.title ?? '動手練習'}</Link>)}
        </div>
      </section>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">里程碑</h2>
        <ol className="space-y-4">
          {project.milestones.map((step, position) => (
            <li key={step.id} className="border-l-4 border-accent pl-4">
              <div className="text-reading font-semibold text-primary">{position + 1}. {step.title}</div>
              <p className="mt-1 text-body leading-7">{step.task}</p>
              <ul className="mt-2 list-disc pl-5 text-ui leading-6 text-text-light">{step.acceptanceCriteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul>
            </li>
          ))}
        </ol>
      </section>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">評量規準</h2>
        <div className="hidden overflow-x-auto md:block">
          <table className="table-soft">
            <thead><tr><th>項目</th><th>比重</th><th>通過證據</th></tr></thead>
            <tbody>{project.rubric.map((row) => <tr key={row.id}><td>{row.criterion}</td><td>{row.weight}%</td><td>{row.passEvidence}</td></tr>)}</tbody>
          </table>
        </div>
        <ul className="space-y-3 md:hidden">
          {project.rubric.map((row) => (
            <li key={row.id} className="rounded-lg border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <span className="text-body font-semibold text-primary">{row.criterion}</span>
                <span className="pill shrink-0">{row.weight}%</span>
              </div>
              <p className="mt-2 text-ui leading-6 text-text-light">通過證據：{row.passEvidence}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default function ProjectsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { index, error, retry } = useLearningIndex()
  if (projectId) return <ProjectDetail id={projectId} />
  if (index === undefined) return <LearningState tone="loading" title="實務專題" />
  if (error) return <LearningState tone="error" title="無法載入實務專題" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!index) return <LearningState tone="empty" title="實務專題尚未開放">目前沒有可閱讀的專題。</LearningState>
  return (
    <div className="page-shell w-full">
      <PageHeader className="mb-5" title="實務專題" description="把學過的單元與實作練習串成一份完整作品，並附上每一步的完成標準。" />
      <div className="grid gap-4 md:grid-cols-2">
        {index.projects.map((project) => (
          <Link className="surface block p-5 no-underline transition hover:border-accent" key={project.id} to={`/projects/${project.id}`}>
            <h2 className="text-reading font-bold text-primary">{project.title}</h2>
          </Link>
        ))}
      </div>
    </div>
  )
}
