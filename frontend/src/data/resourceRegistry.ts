import juniorTocRaw from '@data/toc_manifest.json'
import juniorSubject1Raw from '@data/questions/subject1_questions.json'
import juniorSubject2Raw from '@data/questions/subject2_questions.json'
import juniorMock1Raw from '@data/questions/mock_exam1.json'
import juniorMock2Raw from '@data/questions/mock_exam2.json'
import juniorSampleRaw from '@data/questions/sample_exam.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import middleMock1Raw from '@data-mid/questions/mock_exam1.json'
import middleMock2Raw from '@data-mid/questions/mock_exam2.json'
import middleMock3Raw from '@data-mid/questions/mock_exam3.json'
import guideOutlinesRaw from '../generated/guideOutlines.json'
import type { ExamData, GuideOutlinesData, SubjectQuestions, TocManifest } from '../types'

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
  practiceStatus: ResourceStatus
  practiceLabel: string
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
const guideOutlines = guideOutlinesRaw as GuideOutlinesData

const juniorSubjects = [
  juniorSubject1Raw as SubjectQuestions,
  juniorSubject2Raw as SubjectQuestions,
]
const juniorExams = [
  juniorMock1Raw as ExamData,
  juniorMock2Raw as ExamData,
]
const middleExams = [
  middleMock1Raw as ExamData,
  middleMock2Raw as ExamData,
  middleMock3Raw as ExamData,
]
const juniorSample = juniorSampleRaw as ExamData

export function galleryRoute(level: string, key: string) {
  return `/images?level=${encodeURIComponent(level)}&key=${encodeURIComponent(key)}`
}

function firstGuideRoute(subjectId: string) {
  const guide = guideOutlines.guides[subjectId]
  const first = guide?.root[0]
  return first ? `/guide/${subjectId}/${first}` : undefined
}

function practiceCount(subject: SubjectQuestions) {
  return subject.chapters.reduce((total, chapter) => total + chapter.questions.length, 0)
}

function subjectResources(toc: TocManifest, level: 'junior' | 'middle'): SubjectResource[] {
  return toc.subjects.map((subject, index) => {
    const isJunior = level === 'junior'
    return {
      id: subject.id,
      label: subject.subject,
      shortLabel: subject.subject.split('：')[0],
      guideTo: firstGuideRoute(subject.id),
      overviewTo: `/subject/${subject.id}`,
      practiceTo: isJunior ? `/practice/${subject.id}/${subject.chapters[0]?.id}` : undefined,
      practiceStatus: isJunior ? 'available' : 'pending',
      practiceLabel: isJunior ? '章節練習' : '章節練習待建立',
      examTo: isJunior ? `/exam/mock${index + 1}` : `/exam/mid${index + 1}`,
      chapters: subject.chapters.length,
    }
  })
}

export const resourceStats = {
  junior: {
    subjects: juniorToc.subjects.length,
    chapters: juniorToc.subjects.reduce((total, subject) => total + subject.chapters.length, 0),
    practiceQuestions: juniorSubjects.reduce((total, subject) => total + practiceCount(subject), 0),
    officialQuestions: juniorExams.reduce((total, exam) => total + exam.total, 0) + juniorSample.total,
  },
  middle: {
    subjects: middleToc.subjects.length,
    chapters: middleToc.subjects.reduce((total, subject) => total + subject.chapters.length, 0),
    practiceQuestions: 0,
    officialQuestions: middleExams.reduce((total, exam) => total + exam.total, 0),
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
      detail: `${juniorExams[index]?.total ?? 0} 題`,
      to: `/exam/mock${index + 1}`,
      status: 'available',
    })),
    samples: [{
      label: '初級考試樣題（114年9月版）',
      detail: `${juniorSample.total} 題`,
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
    subtitle: '已有學習指引與公告試題；章節練習題後續建立',
    toc: middleToc,
    subjects: subjectResources(middleToc, 'middle'),
    exams: middleToc.subjects.map((subject, index) => ({
      label: `${subject.subject.split('：')[0]}公告試題`,
      detail: `${middleExams[index]?.total ?? 0} 題`,
      to: `/exam/mid${index + 1}`,
      status: 'available',
    })),
    samples: [{
      label: '中級考試樣題（114年9月版）',
      detail: '官方下載端目前回 404，待補 PDF 入庫',
      status: 'pending',
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
    ],
  },
]
