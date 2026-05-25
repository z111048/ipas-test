import juniorTocRaw from '@data/toc_manifest.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import resourceSummaryRaw from '../generated/resourceSummary.json'
import type { GuideOutlinesData, ResourceSummaryData, TocManifest } from '../types'

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
  codex100PracticeTo?: string
  practiceStatus: ResourceStatus
  practiceLabel: string
  practiceDetail: string
  guideExercisePracticeDetail?: string
  codex100PracticeDetail?: string
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

function subjectResources(toc: TocManifest, level: 'junior' | 'middle'): SubjectResource[] {
  return toc.subjects.map((subject, index) => {
    const isJunior = level === 'junior'
    const subjectSummary = resourceSummary.levels[level].subjects[subject.id]
    const aiSummary = subjectSummary?.ai
    const guideSummary = subjectSummary?.guide
    const codex100Summary = subjectSummary?.codex100
    const hasPracticeQuestions = Boolean(aiSummary?.available)
    const hasCodex100Questions = Boolean(codex100Summary?.available)
    const hasGuideExerciseQuestions = Boolean(guideSummary?.available)
    return {
      id: subject.id,
      label: subject.subject,
      shortLabel: subject.subject.split('：')[0],
      guideTo: firstGuideRoute(subject.id),
      overviewTo: `/subject/${subject.id}`,
      practiceTo: hasPracticeQuestions && aiSummary?.firstChapterId ? `/practice/${subject.id}/${aiSummary.firstChapterId}` : firstGuideRoute(subject.id),
      guideExercisePracticeTo: hasGuideExerciseQuestions && guideSummary?.firstChapterId ? `/practice/${subject.id}/${guideSummary.firstChapterId}/guide` : undefined,
      codex100PracticeTo: hasCodex100Questions && codex100Summary?.firstChapterId ? `/practice/${subject.id}/${codex100Summary.firstChapterId}/codex100` : undefined,
      practiceStatus: hasPracticeQuestions ? 'available' : 'pending',
      practiceLabel: hasPracticeQuestions ? '章節練習' : '章節練習待建立',
      practiceDetail: isJunior ? 'AI 模擬章節練習題' : '原有 AI 模擬章節練習題',
      guideExercisePracticeDetail: hasGuideExerciseQuestions ? `${guideSummary?.total ?? 0} 題，從學習指引 PDF 內嵌練習抽取` : undefined,
      codex100PracticeDetail: hasCodex100Questions ? `${codex100Summary?.total ?? 0} 題，依章節平均分配` : undefined,
      examTo: isJunior ? `/exam/mock${index + 1}` : `/exam/mid${index + 1}`,
      chapters: subject.chapters.length,
    }
  })
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
      (total, subject) => total + (subject.ai?.total ?? 0) + (subject.guide?.total ?? 0) + (subject.codex100?.total ?? 0),
      0
    ),
    officialQuestions: Object.values(resourceSummary.levels.middle.exams).reduce((total, exam) => total + exam.total, 0),
  },
}

export const resourceLevels: LevelResource[] = [
  {
    id: 'junior',
    label: '初級',
    subtitle: '已有章節練習題、公告試題與官方樣題',
    toc: juniorToc,
    subjects: subjectResources(juniorToc, 'junior'),
    exams: juniorToc.subjects.map((subject, index) => ({
      label: `${subject.subject.split('：')[0]}公告試題`,
      detail: `${resourceSummary.levels.junior.exams[`mock${index + 1}`]?.total ?? 0} 題`,
      to: `/exam/mock${index + 1}`,
      status: 'available',
    })),
    samples: [{
      label: '初級考試樣題（114年9月版）',
      detail: `${resourceSummary.levels.junior.exams.sample?.total ?? 0} 題`,
      to: '/exam/sample',
      status: 'available',
    }],
    references: [{
      label: '評鑑內容範圍參考（115簡章）',
      detail: '已入庫，可在圖片與表格檢視',
      to: galleryRoute('共用', 'briefing'),
      status: 'available',
    }],
  },
  {
    id: 'middle',
    label: '中級',
    subtitle: '已有學習指引與公告試題；章節練習內容先集中在學習指引內',
    toc: middleToc,
    subjects: subjectResources(middleToc, 'middle'),
    exams: middleToc.subjects.map((subject, index) => ({
      label: `${subject.subject.split('：')[0]}公告試題`,
      detail: `${resourceSummary.levels.middle.exams[`mid${index + 1}`]?.total ?? 0} 題`,
      to: `/exam/mid${index + 1}`,
      status: 'available',
    })),
    samples: [{
      label: '中級考試樣題（114年9月版）',
      detail: `${resourceSummary.levels.middle.exams.midSample?.total ?? 0} 題`,
      to: '/exam/midSample',
      status: 'available',
    }],
    references: [
      {
        label: '中級學習指引勘誤表',
        detail: '已入庫，可在圖片與表格檢視',
        to: galleryRoute('中級', 'errata'),
        status: 'available',
      },
      {
        label: '評鑑內容範圍參考（115簡章）',
        detail: '已入庫，可在圖片與表格檢視',
        to: galleryRoute('共用', 'briefing'),
        status: 'available',
      },
      {
        label: '中級關鍵字整理',
        detail: '科目一至科目三中英文定義與案例',
        to: '/glossary',
        status: 'available',
      },
    ],
  },
]
