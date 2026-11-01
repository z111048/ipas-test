import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge, PageHeader } from '../../components/ui'
import { findMeta, loadLearningItem, type LearningIndex, type LearningMeta } from './data'
import { localizeTerms } from './displayTerms'
import { ACTION_ROW, READING_MEASURE, READING_PAGE, formatMinutes } from './layout'
import { learnerRepository } from './state/repository'
import type { Lab, LearnerProgress, LearningUnit, Project } from './types'
import { useLearningIndex } from './useLearningIndex'
import { useLearningItem } from './useLearningItem'
import LearningState from './LearningState'
import { previewBadge } from './PreviewBadge'

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
  const terms = new Set<string>()
  const unitTitle = (unitId: string) => localizeTerms(findMeta(index, 'units', unitId)?.title ?? '相關單元')
  return (
    <div className={READING_PAGE}>
      <PageHeader
        className="mb-5"
        eyebrow="實務專題"
        title={localizeTerms(project.title)}
        description={localizeTerms(project.brief.scenario, terms)}
        meta={previewBadge(item.availability)}
        actions={<Link to="/projects" className="btn-secondary">返回實務專題</Link>}
      />
      <section className="surface p-5">
        <h2 className="section-title mb-2">要解決的問題</h2>
        <p className="text-reading leading-7">{localizeTerms(project.brief.problemStatement, terms)}</p>
        {(project.unitRefs.length > 0 || project.labRefs.length > 0) && (
          <div className={`mt-4 ${ACTION_ROW}`}>
            {project.labRefs.map((ref) => <Link className="btn-primary" key={ref.id} to={`/labs/${ref.id}`}>實作：{localizeTerms(findMeta(index, 'labs', ref.id)?.title ?? '動手練習')}</Link>)}
            {project.unitRefs.map((ref) => <Link className="btn-secondary" key={ref.id} to={`/learn/${ref.id}`}>先學：{unitTitle(ref.id)}</Link>)}
          </div>
        )}
      </section>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">里程碑</h2>
        <ol className="space-y-4">
          {project.milestones.map((step, position) => (
            <li key={step.id} className="border-l-4 border-accent pl-4">
              <div className="text-reading font-semibold text-primary">{position + 1}. {localizeTerms(step.title, terms)}</div>
              <p className="mt-1 text-body leading-7">{localizeTerms(step.task, terms)}</p>
              <ul className="mt-2 list-disc pl-5 text-ui leading-6 text-text-light">{step.acceptanceCriteria.map((criterion) => <li key={criterion}>{localizeTerms(criterion, terms)}</li>)}</ul>
              {step.requiredUnitIds.length > 0 && (
                <p className="mt-2 text-meta text-text-light">
                  相關單元：{step.requiredUnitIds.map((unitId, order) => (
                    <span key={unitId}>{order > 0 && '、'}<Link className="underline decoration-accent/50 underline-offset-2 hover:text-accent" to={`/learn/${unitId}`}>{unitTitle(unitId)}</Link></span>
                  ))}
                </p>
              )}
            </li>
          ))}
        </ol>
      </section>
      <section className="surface mt-4 p-5">
        <h2 className="section-title mb-3">評量規準</h2>
        <div className="hidden overflow-x-auto md:block">
          <table className="table-soft">
            <thead><tr><th>項目</th><th>比重</th><th>通過證據</th></tr></thead>
            <tbody>{project.rubric.map((row) => <tr key={row.id}><td>{localizeTerms(row.criterion, terms)}</td><td>{row.weight}%</td><td>{localizeTerms(row.passEvidence, terms)}</td></tr>)}</tbody>
          </table>
        </div>
        <ul className="space-y-3 md:hidden">
          {project.rubric.map((row) => (
            <li key={row.id} className="rounded-lg border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <span className="text-body font-semibold text-primary">{localizeTerms(row.criterion)}</span>
                <span className="pill shrink-0">{row.weight}%</span>
              </div>
              <p className="mt-2 text-ui leading-6 text-text-light">通過證據：{localizeTerms(row.passEvidence)}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

interface ProjectOverview {
  project: Project
  unitMinutes: number
  labMinutes: number
  labsTotal: number
  labsDone: number
  labsOpened: number
}

type OverviewState = { status: 'loading' } | { status: 'ready'; value: ProjectOverview; progressKnown: boolean } | { status: 'error' }

function isTracked(row: LearnerProgress, ref: { id: string; revision: number }) {
  return row.target.kind === 'lab' && row.target.id === ref.id && row.target.revision === ref.revision
}

/** 卡片需要的概要：情境取自專題本身，時間由單元與實作步驟的預估分鐘加總，進度取自本機的實作自評紀錄。 */
function useProjectOverviews(index: LearningIndex | null | undefined) {
  const [overviews, setOverviews] = useState<Record<string, OverviewState>>({})
  useEffect(() => {
    if (!index) return
    let active = true
    setOverviews(Object.fromEntries(index.projects.map((meta) => [meta.id, { status: 'loading' } as OverviewState])))
    const progressPromise = learnerRepository.listProgress().then((rows) => ({ rows, known: true }), () => ({ rows: [] as LearnerProgress[], known: false }))
    const readUnitMinutes = async (ref: { id: string }) => {
      const meta = findMeta(index, 'units', ref.id)
      return meta ? (await loadLearningItem<LearningUnit>(meta.path)).document.estimatedMinutes ?? 0 : 0
    }
    const readLabMinutes = async (ref: { id: string }) => {
      const meta = findMeta(index, 'labs', ref.id)
      return meta ? (await loadLearningItem<Lab>(meta.path)).document.steps.reduce((sum, step) => sum + (step.estimatedMinutes ?? 0), 0) : 0
    }
    const total = (values: number[]) => values.reduce((sum, value) => sum + value, 0)
    index.projects.forEach((meta) => {
      loadLearningItem<Project>(meta.path)
        .then(async ({ document: project }) => {
          const [unitMinutes, labMinutes, progress] = await Promise.all([
            Promise.all(project.unitRefs.map(readUnitMinutes)).then(total),
            Promise.all(project.labRefs.map(readLabMinutes)).then(total),
            progressPromise,
          ])
          const labRows = project.labRefs.map((ref) => progress.rows.find((row) => isTracked(row, ref)))
          const value: ProjectOverview = {
            project,
            unitMinutes,
            labMinutes,
            labsTotal: project.labRefs.length,
            labsDone: labRows.filter((row) => row?.state === 'self_reported_complete').length,
            labsOpened: labRows.filter((row) => row && row.state !== 'self_reported_complete').length,
          }
          if (active) setOverviews((current) => ({ ...current, [meta.id]: { status: 'ready', value, progressKnown: progress.known } }))
        })
        .catch(() => { if (active) setOverviews((current) => ({ ...current, [meta.id]: { status: 'error' } })) })
    })
    return () => { active = false }
  }, [index])
  return overviews
}

function ProgressSummary({ overview, known }: { overview: ProjectOverview; known: boolean }) {
  if (!known) return <p className="text-ui text-text-light">這個瀏覽器無法讀取學習紀錄，進度暫不顯示。</p>
  if (overview.labsTotal === 0) return <p className="text-ui text-text-light">這份專題沒有實作練習，請依里程碑自行核對。</p>
  const percent = Math.round((overview.labsDone / overview.labsTotal) * 100)
  const status = overview.labsDone === overview.labsTotal
    ? '實作練習已自評完成'
    : overview.labsOpened > 0 || overview.labsDone > 0 ? '實作進行中' : '尚未開始'
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-ui">
        <span className="font-semibold text-primary">{status}</span>
        <span className="text-text-light">實作 {overview.labsDone} / {overview.labsTotal}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-border" aria-hidden="true">
        <div className="h-full rounded-full bg-answered" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-2 text-meta text-text-light">依你在實作練習頁的自評紀錄計算，只存在這個瀏覽器。</p>
    </div>
  )
}

function ProjectCard({ meta, state, featured }: { meta: LearningMeta; state: OverviewState | undefined; featured: boolean }) {
  const ready = state?.status === 'ready' ? state : undefined
  const overview = ready?.value
  const terms = new Set<string>()
  const totalMinutes = overview ? overview.unitMinutes + overview.labMinutes : 0
  const started = overview && (overview.labsDone > 0 || overview.labsOpened > 0)
  const cta = <Link className="btn-primary w-full sm:w-auto" to={`/projects/${meta.id}`}>{started ? '繼續專題' : '查看專題'}</Link>

  const facts = overview && (
    <dl className="grid gap-3 text-ui">
      {totalMinutes > 0 && (
        <div>
          <dt className="text-meta text-text-light">預估時間</dt>
          <dd className="font-semibold text-primary">{formatMinutes(totalMinutes)}</dd>
          <dd className="text-meta text-text-light">
            {[overview.unitMinutes > 0 && `閱讀 ${overview.project.unitRefs.length} 個單元 ${overview.unitMinutes} 分鐘`, overview.labMinutes > 0 && `實作 ${overview.labMinutes} 分鐘`].filter(Boolean).join('＋')}
          </dd>
        </div>
      )}
      <div>
        <dt className="text-meta text-text-light">里程碑</dt>
        <dd className="font-semibold text-primary">{overview.project.milestones.length} 個</dd>
      </div>
      <div>
        <dt className="text-meta text-text-light">進度</dt>
        <dd className="mt-1"><ProgressSummary overview={overview} known={ready.progressKnown} /></dd>
      </div>
    </dl>
  )

  return (
    <article className={`surface p-5 ${featured ? 'sm:p-6' : 'flex flex-col'}`} aria-labelledby={`project-${meta.id}`}>
      <div className={featured ? 'grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]' : 'flex flex-1 flex-col'}>
        <div className="min-w-0">
          <h2 id={`project-${meta.id}`} className="text-reading font-bold text-primary">{localizeTerms(meta.title)}</h2>
          {state?.status === 'loading' && <p className="mt-2 text-ui text-text-light">正在讀取專題概要…</p>}
          {state?.status === 'error' && <p className="mt-2 text-ui text-text-light">專題概要暫時無法載入，仍可直接開啟專題。</p>}
          {overview && (
            <>
              <p className={`mt-2 text-body leading-7 text-app-text ${READING_MEASURE}`}>{localizeTerms(overview.project.brief.scenario, terms)}</p>
              {featured && (
                <>
                  <h3 className="mt-5 text-meta font-semibold text-text-light">要解決的問題</h3>
                  <p className={`mt-1 text-ui leading-6 text-text-light ${READING_MEASURE}`}>{localizeTerms(overview.project.brief.problemStatement, terms)}</p>
                  {overview.project.milestones.length > 0 && (
                    <>
                      <h3 className="mt-5 text-meta font-semibold text-text-light">完成路線</h3>
                      <ol className="mt-2 grid gap-2 sm:grid-cols-2">
                        {overview.project.milestones.map((step, position) => (
                          <li key={step.id} className="flex items-start gap-2 rounded-lg border border-border px-3 py-2 text-ui leading-6">
                            <Badge tone="accent" className="shrink-0">{position + 1}</Badge>
                            <span>{localizeTerms(step.title, terms)}</span>
                          </li>
                        ))}
                      </ol>
                    </>
                  )}
                </>
              )}
            </>
          )}
          {!featured && overview && <div className="mt-4">{facts}</div>}
          {!featured && <div className="mt-auto pt-4">{cta}</div>}
        </div>
        {featured && (
          <aside className="flex flex-col gap-4 rounded-lg border border-border bg-unanswered-soft p-4" aria-label="專題概要">
            {facts}
            <div className="mt-auto">{cta}</div>
          </aside>
        )}
      </div>
    </article>
  )
}

export default function ProjectsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { index, error, retry } = useLearningIndex()
  const overviews = useProjectOverviews(projectId ? undefined : index)
  if (projectId) return <ProjectDetail id={projectId} />
  if (index === undefined) return <LearningState tone="loading" title="實務專題" />
  if (error) return <LearningState tone="error" title="無法載入實務專題" action={<button type="button" className="btn-secondary" onClick={retry}>重試</button>}>{error}</LearningState>
  if (!index || index.projects.length === 0) return <LearningState tone="empty" title="實務專題尚未開放">目前沒有可閱讀的專題。</LearningState>
  const featured = index.projects.length === 1
  return (
    <div className="page-shell w-full">
      <PageHeader className="mb-5" title="實務專題" description="把學過的單元與實作練習串成一份完整作品，並附上每一步的完成標準。" />
      <div className={featured ? 'grid gap-4' : 'grid gap-4 md:grid-cols-2'}>
        {index.projects.map((meta) => <ProjectCard key={meta.id} meta={meta} state={overviews[meta.id]} featured={featured} />)}
      </div>
    </div>
  )
}
