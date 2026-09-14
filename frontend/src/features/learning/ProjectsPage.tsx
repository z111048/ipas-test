import { Link, useParams } from 'react-router-dom'
import { PageHeader, StatePanel } from '../../components/ui'
import { findMeta } from './data'
import type { Project } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'

function ProjectDetail({ id }: { id: string }) {
  const { index, error: indexError, retry: retryIndex } = useLearningIndex()
  const meta = index ? findMeta(index, 'projects', id) : undefined
  const { item, error, retry } = useLearningItem<Project>('project', meta?.path)
  if (index === undefined) return <StatePanel tone="loading" title="載入專題" />
  if (indexError) return <StatePanel tone="error" title="無法載入專題" action={<button className="btn-secondary" onClick={retryIndex}>重試</button>}>{indexError}</StatePanel>
  if (!index || !meta) return <StatePanel tone="empty" title="找不到專題"><Link to="/projects">返回專題列表</Link></StatePanel>
  if (error) return <StatePanel tone="error" title="專題載入失敗" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!item) return <StatePanel tone="loading" title="載入專題" />
  const project = item.document
  return <div className="page-shell w-full">{import.meta.env.DEV && item.availability === 'preview' && <div className="alert-warning mb-4" data-learning-preview>開發預覽：此專題尚未正式發布。</div>}<PageHeader eyebrow="成果專題" title={project.title} description={project.brief.scenario} /><section className="surface p-5"><h2 className="section-title mb-2">要解決的問題</h2><p className="leading-7">{project.brief.problemStatement}</p><div className="mt-4 flex flex-wrap gap-2">{project.unitRefs.map((ref) => <Link className="btn-secondary" key={ref.id} to={`/learn/${ref.id}`}>先學：{ref.id}</Link>)}{project.labRefs.map((ref) => <Link className="btn-secondary" key={ref.id} to={`/labs/${ref.id}`}>實作 Lab</Link>)}</div></section><section className="surface mt-4 p-5"><h2 className="section-title mb-3">里程碑</h2><ol className="space-y-4">{project.milestones.map((step, index) => <li key={step.id} className="border-l-4 border-accent pl-4"><div className="font-semibold text-primary">{index + 1}. {step.title}</div><p className="mt-1 text-sm leading-6">{step.task}</p><ul className="mt-2 list-disc pl-5 text-sm text-text-light">{step.acceptanceCriteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul></li>)}</ol></section><section className="surface mt-4 overflow-x-auto p-5"><h2 className="section-title mb-3">評量規準</h2><table className="table-soft"><thead><tr><th>項目</th><th>比重</th><th>通過證據</th></tr></thead><tbody>{project.rubric.map((row) => <tr key={row.id}><td>{row.criterion}</td><td>{row.weight}%</td><td>{row.passEvidence}</td></tr>)}</tbody></table></section></div>
}

export default function ProjectsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { index, error, retry } = useLearningIndex()
  if (projectId) return <ProjectDetail id={projectId} />
  if (index === undefined) return <StatePanel tone="loading" title="載入專題" />
  if (error) return <StatePanel tone="error" title="無法載入專題" action={<button className="btn-secondary" onClick={retry}>重試</button>}>{error}</StatePanel>
  if (!index) return <StatePanel tone="empty" title="專題尚未發布" />
  return <div className="page-shell w-full"><PageHeader eyebrow="做中學" title="實務專題" description="把單元、Lab 與交付成果串成可檢查的工作。" /><div className="grid gap-4 md:grid-cols-2">{index.projects.map((project) => <Link className="surface block p-5 no-underline hover:border-accent" key={project.id} to={`/projects/${project.id}`}><h2 className="font-bold text-primary">{project.title}</h2></Link>)}</div></div>
}
