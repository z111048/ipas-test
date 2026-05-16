import { Link, useParams } from 'react-router-dom'
import { useEffect } from 'react'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import { resourceLevels } from '../data/resourceRegistry'
import type { SubjectQuestions } from '../types'
import QuestionCard from '../components/practice/QuestionCard'

const questionData: Record<string, SubjectQuestions> = {
  s1: s1q as SubjectQuestions,
  s2: s2q as SubjectQuestions,
}

export default function PracticePage() {
  const { subjectId, chapterId } = useParams<{ subjectId: string; chapterId: string }>()
  const data = subjectId ? questionData[subjectId] : undefined
  const chapter = data?.chapters.find((c) => c.id === chapterId)
  const level = resourceLevels.find((item) => item.subjects.some((subject) => subject.id === subjectId))
  const subject = level?.subjects.find((item) => item.id === subjectId)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [chapterId])

  if (!data || subject?.practiceStatus === 'pending') {
    return (
      <div>
        <div className="text-2xl font-bold text-primary mb-1">章節練習題待建立</div>
        <div className="text-text-light mb-5">
          {subject?.label ?? subjectId} 的 AI 模擬章節練習題尚未入庫。
        </div>
        <div className="rounded-lg border border-[#f2d28b] bg-[#fff8e6] text-[#7a5700] px-4 py-3 mb-5 text-[0.9rem]">
          目前中級可先使用學習指引與公告試題；後續完成 AI 模擬題後，此入口會自動改為可練習。
        </div>
        <div className="flex flex-wrap gap-2">
          {subject?.guideTo && (
            <Link
              to={subject.guideTo}
              className="text-[0.85rem] px-3 py-1.5 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
            >
              前往學習指引
            </Link>
          )}
          {subject?.examTo && (
            <Link
              to={subject.examTo}
              className="text-[0.85rem] px-3 py-1.5 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
            >
              前往公告試題
            </Link>
          )}
        </div>
      </div>
    )
  }

  if (!chapter) {
    return <div className="text-error p-4">找不到章節：{chapterId}</div>
  }

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">{chapter.title}</div>
      <div className="text-text-light mb-5">
        {data.subject} › {chapter.title}（共 {chapter.questions.length} 題）
      </div>
      <div>
        {chapter.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} index={i} />
        ))}
      </div>
    </div>
  )
}
