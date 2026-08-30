import juniorTocRaw from '@data/toc_manifest.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import resourceSummaryRaw from '../generated/resourceSummary.json'
import type { GuideOutlinesData, ResourceSummaryData, TocManifest } from '../types'
import {
  catalogLevels,
  examsForLevel,
  resourcesForLevel,
  type CatalogExam,
  type CatalogResource,
  type ResourceLevelId,
} from './resourceCatalog'

export type ResourceStatus = 'available' | 'pending' | 'external'

export interface ResourceNavItem {
  label: string
  detail?: string
  to?: string
  externalUrl?: string
  status?: ResourceStatus
}

export interface SubjectResource {
  id: string
  label: string
  shortLabel: string
  guideTo?: string
  overviewTo?: string
  practiceTo?: string
  guideExercisePracticeTo?: string
  practiceStatus: ResourceStatus
  practiceLabel: string
  practiceDetail: string
  guideExercisePracticeDetail?: string
  examTo?: string
  chapters: number
}

export interface LevelResource {
  id: 'junior' | 'middle'
  label: string
  subtitle: string
  toc: TocManifest
  subjects: SubjectResource[]
  exams: ResourceNavItem[]
  samples: ResourceNavItem[]
  references: ResourceNavItem[]
}

const juniorToc = juniorTocRaw as TocManifest
const middleToc = middleTocRaw as TocManifest
const guideOutlines = guideOutlinesRaw as unknown as GuideOutlinesData
export const resourceSummary = resourceSummaryRaw as unknown as ResourceSummaryData

export function galleryRoute(level: string, key: string) {
  return `/images?level=${encodeURIComponent(level)}&key=${encodeURIComponent(key)}`
}

function firstGuideRoute(subjectId: string) {
  const guide = guideOutlines.guides[subjectId]
  const first = guide?.root[0]
  return first ? `/guide/${subjectId}/${first}` : undefined
}

function subjectResources(toc: TocManifest, level: ResourceLevelId): SubjectResource[] {
  return toc.subjects.map((subject) => {
    const subjectSummary = resourceSummary.levels[level].subjects[subject.id]
    const aiSummary = subjectSummary?.ai
    const guideSummary = subjectSummary?.guide
    const hasPracticeQuestions = Boolean(aiSummary?.available)
    const hasGuideExerciseQuestions = Boolean(guideSummary?.available)
    const latestExam = examsForLevel(level).find(
      (exam) => exam.kind === 'official' && exam.subjectId === subject.id
    )
    return {
      id: subject.id,
      label: subject.subject,
      shortLabel: subject.subject.split('：')[0],
      guideTo: firstGuideRoute(subject.id),
      overviewTo: `/subject/${subject.id}`,
      practiceTo: hasPracticeQuestions && aiSummary?.firstChapterId ? `/practice/${subject.id}/${aiSummary.firstChapterId}` : firstGuideRoute(subject.id),
      guideExercisePracticeTo: hasGuideExerciseQuestions && guideSummary?.firstChapterId ? `/practice/${subject.id}/${guideSummary.firstChapterId}/guide` : undefined,
      practiceStatus: hasPracticeQuestions ? 'available' : 'pending',
      practiceLabel: hasPracticeQuestions ? '章節練習' : '章節練習待建立',
      practiceDetail: '章節模擬練習題',
      guideExercisePracticeDetail: hasGuideExerciseQuestions ? `${guideSummary?.total ?? 0} 題，從學習指引 PDF 內嵌練習抽取` : undefined,
      examTo: latestExam ? `/exam/${latestExam.routeKey}` : undefined,
      chapters: subject.chapters.length,
    }
  })
}

function examNavItem(exam: CatalogExam): ResourceNavItem {
  const summary = resourceSummary.levels[exam.levelId].exams[exam.routeKey]
  const available = Boolean(summary?.available)
  return {
    label: exam.label,
    detail: `${summary?.total ?? 0} 題`,
    to: available ? `/exam/${exam.routeKey}` : undefined,
    status: available ? 'available' : 'pending',
  }
}

function referenceNavItem(resource: CatalogResource): ResourceNavItem {
  const to = resource.kind === 'route'
    ? resource.route
    : resource.sourceLevel && resource.sourceKey
      ? galleryRoute(resource.sourceLevel, resource.sourceKey)
      : undefined
  return {
    label: resource.label,
    detail: resource.detail,
    to,
    status: to ? 'available' : 'pending',
  }
}

export const resourceStats = {
  junior: {
    subjects: juniorToc.subjects.length,
    chapters: juniorToc.subjects.reduce((total, subject) => total + subject.chapters.length, 0),
    practiceQuestions: Object.values(resourceSummary.levels.junior.subjects).reduce(
      (total, subject) => total + (subject.ai?.total ?? 0) + (subject.guide?.total ?? 0),
      0
    ),
    officialQuestions: Object.values(resourceSummary.levels.junior.exams).reduce((total, exam) => total + exam.total, 0),
  },
  middle: {
    subjects: middleToc.subjects.length,
    chapters: middleToc.subjects.reduce((total, subject) => total + subject.chapters.length, 0),
    practiceQuestions: Object.values(resourceSummary.levels.middle.subjects).reduce(
      (total, subject) => total + (subject.ai?.total ?? 0) + (subject.guide?.total ?? 0),
      0
    ),
    officialQuestions: Object.values(resourceSummary.levels.middle.exams).reduce((total, exam) => total + exam.total, 0),
  },
}

const tocByLevel: Record<ResourceLevelId, TocManifest> = {
  junior: juniorToc,
  middle: middleToc,
}

export const resourceLevels: LevelResource[] = catalogLevels.map((level) => {
  const toc = tocByLevel[level.id]
  const exams = examsForLevel(level.id)
  return {
    id: level.id,
    label: level.label,
    subtitle: level.subtitle,
    toc,
    subjects: subjectResources(toc, level.id),
    exams: exams.filter((exam) => exam.kind === 'official').map(examNavItem),
    samples: exams.filter((exam) => exam.kind === 'sample').map(examNavItem),
    references: resourcesForLevel(level.id).map(referenceNavItem),
  }
})
