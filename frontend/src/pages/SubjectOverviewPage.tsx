import { Link, useParams } from 'react-router-dom'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import tocRaw from '@data/toc_manifest.json'
import type { SubjectQuestions, TocManifest } from '../types'
import ProgressBar from '../components/shared/ProgressBar'

const subject1 = s1q as SubjectQuestions
const subject2 = s2q as SubjectQuestions
const toc = tocRaw as TocManifest

export default function SubjectOverviewPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const isS1 = subjectId === 's1'
  const subjectData = isS1 ? toc.subjects[0] : toc.subjects[1]
  const data = isS1 ? subject1 : subject2
  const maxQ = Math.max(...data.chapters.map((c) => c.questions.length), 1)

  const questionsByChapter = Object.fromEntries(
    data.chapters.map((c) => [c.id, c.questions.length])
  )

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">{subjectData.subject}</div>
      <div className="text-text-light mb-5">
        評鑑主題：{subjectData.chapters.map((c) => c.title).join(' / ')}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {subjectData.chapters.map((ch) => {
          const pageRange = ch.page_range
            ? `PDF 第 ${ch.page_range[0] + 1}–${ch.page_range[1] + 1} 頁`
            : null
          return (
            <div key={ch.id} className="bg-card rounded-xl shadow-sm border border-border p-5">
              <h3 className="text-primary font-semibold mb-1">{ch.title}</h3>
              {pageRange && (
                <div className="text-[0.75rem] text-text-light mb-3">{pageRange}</div>
              )}
              <div className="flex flex-wrap gap-1 mb-4">
                {ch.subtopics.map((t) => (
                  <span key={t} className="text-[0.75rem] bg-[#eef5ff] text-accent px-2 py-0.5 rounded-full">{t}</span>
                ))}
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/guide/${subjectId}/${ch.id}`}
                  className="text-[0.8rem] px-3 py-1 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
                >
                  📖 學習指引
                </Link>
                <Link
                  to={`/practice/${subjectId}/${ch.id}`}
                  className="text-[0.8rem] px-3 py-1 rounded-lg border border-accent text-accent hover:bg-accent hover:text-white transition-colors no-underline"
                >
                  ✏️ 練習題
                </Link>
              </div>
            </div>
          )
        })}
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5">
        <h2 className="text-lg font-semibold text-primary mb-4">章節練習題數量</h2>
        <div className="space-y-3">
          {data.chapters.map((ch) => {
            const n = ch.questions.length
            return (
              <div key={ch.id}>
                <div className="flex justify-between text-[0.85rem] mb-1">
                  <span>{ch.title}</span>
                  <span className="text-accent font-semibold">{n} 題</span>
                </div>
                <ProgressBar percent={(n / maxQ) * 100} />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
