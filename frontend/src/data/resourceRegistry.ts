import juniorTocRaw from '@data/toc_manifest.json'
import juniorSubject1Raw from '@data/questions/subject1_questions.json'
import juniorSubject2Raw from '@data/questions/subject2_questions.json'
import juniorMock1Raw from '@data/questions/mock_exam1.json'
import juniorMock2Raw from '@data/questions/mock_exam2.json'
import juniorSampleRaw from '@data/questions/sample_exam.json'
import middleTocRaw from '@data-mid/toc_manifest.json'
import middleSubject1Raw from '@data-mid/questions/subject1_questions.json'
import middleSubject2Raw from '@data-mid/questions/subject2_questions.json'
import middleSubject3Raw from '@data-mid/questions/subject3_questions.json'
import middleMock1Raw from '@data-mid/questions/mock_exam1.json'
import middleMock2Raw from '@data-mid/questions/mock_exam2.json'
import middleMock3Raw from '@data-mid/questions/mock_exam3.json'
import middleSampleRaw from '@data-mid/questions/sample_exam.json'
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
  practiceDetail: string
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
const middleSample = middleSampleRaw as ExamData
const subjectQuestionsById: Record<string, SubjectQuestions> = {
  s1: juniorSubject1Raw as SubjectQuestions,
  s2: juniorSubject2Raw as SubjectQuestions,
  'mid-s1': middleSubject1Raw as SubjectQuestions,
  'mid-s2': middleSubject2Raw as SubjectQuestions,
  'mid-s3': middleSubject3Raw as SubjectQuestions,
}

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

function subjectQuestionCount(subjectId: string) {
  const subject = subjectQuestionsById[subjectId]
  return subject?.chapters.reduce((total, chapter) => total + chapter.questions.length, 0) ?? 0
}

function subjectResources(toc: TocManifest, level: 'junior' | 'middle'): SubjectResource[] {
  return toc.subjects.map((subject, index) => {
    const isJunior = level === 'junior'
    const hasPracticeQuestions = subjectQuestionCount(subject.id) > 0
    return {
      id: subject.id,
      label: subject.subject,
      shortLabel: subject.subject.split('：')[0],
      guideTo: firstGuideRoute(subject.id),
      overviewTo: `/subject/${subject.id}`,
      practiceTo: hasPracticeQuestions ? `/practice/${subject.id}/${subject.chapters[0]?.id}` : firstGuideRoute(subject.id),
      practiceStatus: hasPracticeQuestions ? 'available' : 'pending',
      practiceLabel: hasPracticeQuestions ? '章節練習' : '章節練習待建立',
      practiceDetail: isJunior ? 'AI 模擬章節練習題' : '中級 AI 模擬題資料結構已建立，待產生章節題',
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
    practiceQuestions: ['mid-s1', 'mid-s2', 'mid-s3'].reduce((total, subjectId) => total + subjectQuestionCount(subjectId), 0),
    officialQuestions: middleExams.reduce((total, exam) => total + exam.total, 0) + middleSample.total,
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
    subtitle: '已有學習指引與公告試題；章節練習內容先集中在學習指引內',
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
      detail: `${middleSample.total} 題`,
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
        detail: '科目一、科目三中英文定義與案例',
        to: '/glossary',
        status: 'available',
      },
    ],
  },
]
