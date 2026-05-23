import { Link, useParams } from 'react-router-dom'
import { useEffect } from 'react'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import s1GuideExerciseQ from '@data/questions/subject1_guide_exercises.json'
import s2GuideExerciseQ from '@data/questions/subject2_guide_exercises.json'
import midS1q from '@data-mid/questions/subject1_questions.json'
import midS2q from '@data-mid/questions/subject2_questions.json'
import midS3q from '@data-mid/questions/subject3_questions.json'
import midS1GuideExerciseQ from '@data-mid/questions/subject1_guide_exercises.json'
import midS2GuideExerciseQ from '@data-mid/questions/subject2_guide_exercises.json'
import midS3GuideExerciseQ from '@data-mid/questions/subject3_guide_exercises.json'
import midS1Codex100q from '@data-mid/questions/subject1_codex100_questions.json'
import midS2Codex100q from '@data-mid/questions/subject2_codex100_questions.json'
import midS3Codex100q from '@data-mid/questions/subject3_codex100_questions.json'
import { resourceLevels } from '../data/resourceRegistry'
import type { SubjectQuestions } from '../types'
import QuestionCard from '../components/practice/QuestionCard'

const questionData: Record<string, SubjectQuestions> = {
  s1: s1q as SubjectQuestions,
  s2: s2q as SubjectQuestions,
  'mid-s1': midS1q as SubjectQuestions,
  'mid-s2': midS2q as SubjectQuestions,
  'mid-s3': midS3q as SubjectQuestions,
}

const codex100QuestionData: Record<string, SubjectQuestions> = {
  'mid-s1': midS1Codex100q as SubjectQuestions,
  'mid-s2': midS2Codex100q as SubjectQuestions,
  'mid-s3': midS3Codex100q as SubjectQuestions,
}

const guideExerciseQuestionData: Record<string, SubjectQuestions> = {
  s1: s1GuideExerciseQ as SubjectQuestions,
  s2: s2GuideExerciseQ as SubjectQuestions,
  'mid-s1': midS1GuideExerciseQ as SubjectQuestions,
  'mid-s2': midS2GuideExerciseQ as SubjectQuestions,
  'mid-s3': midS3GuideExerciseQ as SubjectQuestions,
}

export default function PracticePage() {
  const { subjectId, chapterId, practiceSet } = useParams<{ subjectId: string; chapterId: string; practiceSet?: string }>()
  const isCodex100 = practiceSet === 'codex100'
  const isGuideExercise = practiceSet === 'guide'
  const data = subjectId
    ? isCodex100
      ? codex100QuestionData[subjectId]
      : isGuideExercise
        ? guideExerciseQuestionData[subjectId]
        : questionData[subjectId]
    : undefined
  const originalData = subjectId ? questionData[subjectId] : undefined
  const codex100Data = subjectId ? codex100QuestionData[subjectId] : undefined
  const guideExerciseData = subjectId ? guideExerciseQuestionData[subjectId] : undefined
  const originalChapter = originalData?.chapters.find((c) => c.id === chapterId)
  const codex100Chapter = codex100Data?.chapters.find((c) => c.id === chapterId)
  const guideExerciseChapter = guideExerciseData?.chapters.find((c) => c.id === chapterId)
  const chapter = data?.chapters.find((c) => c.id === chapterId)
  const practiceSetSuffix = isCodex100 ? '/codex100' : isGuideExercise ? '/guide' : ''
  const chapterRoute = (targetChapterId: string) =>
    `/practice/${subjectId}/${targetChapterId}${practiceSetSuffix}`
  const level = resourceLevels.find((item) => item.subjects.some((subject) => subject.id === subjectId))
  const subject = level?.subjects.find((item) => item.id === subjectId)
  const setLabel = isCodex100 ? 'Codex 100 題' : isGuideExercise ? '學習指引練習' : 'AI 舊版練習'
  const selectableChapters = data?.chapters.filter((item) => !isGuideExercise || item.questions.length > 0) ?? []

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [chapterId, practiceSet])

  if (isGuideExercise && data && chapter && chapter.questions.length === 0) {
    return (
      <div>
        <div className="text-2xl font-bold text-primary mb-1">本章沒有學習指引練習題</div>
        <div className="text-text-light mb-5">
          {data.subject} › {chapter.title} 在學習指引 PDF 內沒有內嵌章節練習題。
        </div>
        {selectableChapters.length > 0 && (
          <div className="bg-card rounded-lg border border-border p-3 mb-5">
            <div className="text-[0.78rem] font-semibold text-text-light mb-2">可練習章節</div>
            <div className="flex flex-wrap gap-2">
              {selectableChapters.map((item) => (
                <Link
                  key={item.id}
                  to={`/practice/${subjectId}/${item.id}/guide`}
                  className="text-[0.8rem] px-3 py-1.5 rounded-lg border border-[#9a5c17] text-[#9a5c17] hover:bg-[#9a5c17] hover:text-white transition-colors no-underline"
                >
                  {item.title}（{item.questions.length} 題）
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (!data || (!isCodex100 && !isGuideExercise && subject?.practiceStatus === 'pending') || chapter?.questions.length === 0) {
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
        {data.subject} › {chapter.title} › {setLabel}（共 {chapter.questions.length} 題）
      </div>
      <div className="flex flex-wrap gap-2 mb-5">
        {originalChapter && originalChapter.questions.length > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}`}
            className={`text-[0.85rem] px-3 py-1.5 rounded-lg border transition-colors no-underline ${
              !isCodex100 && !isGuideExercise
                ? 'border-accent bg-accent text-white'
                : 'border-border text-text-light hover:border-accent hover:text-accent'
            }`}
          >
            AI 舊版練習（{originalChapter.questions.length} 題）
          </Link>
        )}
        {guideExerciseChapter && guideExerciseChapter.questions.length > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}/guide`}
            className={`text-[0.85rem] px-3 py-1.5 rounded-lg border transition-colors no-underline ${
              isGuideExercise
                ? 'border-[#9a5c17] bg-[#9a5c17] text-white'
                : 'border-border text-text-light hover:border-[#9a5c17] hover:text-[#9a5c17]'
            }`}
          >
            學習指引練習（{guideExerciseChapter.questions.length} 題）
          </Link>
        )}
        {codex100Chapter && codex100Chapter.questions.length > 0 && (
          <Link
            to={`/practice/${subjectId}/${chapterId}/codex100`}
            className={`text-[0.85rem] px-3 py-1.5 rounded-lg border transition-colors no-underline ${
              isCodex100
                ? 'border-[#5b7c2a] bg-[#5b7c2a] text-white'
                : 'border-border text-text-light hover:border-[#5b7c2a] hover:text-[#5b7c2a]'
            }`}
          >
            Codex 100 題（{codex100Chapter.questions.length} 題）
          </Link>
        )}
      </div>
      {selectableChapters.length > 1 && (
        <div className="bg-card rounded-lg border border-border p-3 mb-5">
          <div className="text-[0.78rem] font-semibold text-text-light mb-2">切換章節</div>
          <div className="flex flex-wrap gap-2">
            {selectableChapters.map((item, index) => {
              const count = item.questions.length
              return (
                <Link
                  key={item.id}
                  to={chapterRoute(item.id)}
                  className={`text-[0.8rem] px-3 py-1.5 rounded-lg border transition-colors no-underline ${
                    item.id === chapter.id
                      ? 'border-accent bg-accent text-white'
                      : 'border-border text-text-light hover:border-accent hover:text-accent'
                  }`}
                  title={item.title}
                >
                  {index + 1}. {item.title}（{count} 題）
                </Link>
              )
            })}
          </div>
        </div>
      )}
      <div>
        {chapter.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} index={i} />
        ))}
      </div>
    </div>
  )
}
