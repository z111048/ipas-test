import { useParams } from 'react-router-dom'
import { useEffect } from 'react'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import tocRaw from '@data/toc_manifest.json'
import type { SubjectQuestions, TocManifest } from '../types'
import QuestionCard from '../components/practice/QuestionCard'

const subject1 = s1q as SubjectQuestions
const subject2 = s2q as SubjectQuestions
const toc = tocRaw as TocManifest

export default function PracticePage() {
  const { subjectId, chapterId } = useParams<{ subjectId: string; chapterId: string }>()

  const data = subjectId === 's1' ? subject1 : subject2
  const chapter = data.chapters.find((c) => c.id === chapterId)
  const subjectLabel = toc.subjects.find((s) => s.id === subjectId)?.subject ?? data.subject

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [chapterId])

  if (!chapter) {
    return <div className="text-error p-4">找不到章節：{chapterId}</div>
  }

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">{chapter.title}</div>
      <div className="text-text-light mb-5">
        {subjectLabel} › {chapter.title}（共 {chapter.questions.length} 題）
      </div>
      <div>
        {chapter.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} index={i} />
        ))}
      </div>
    </div>
  )
}
