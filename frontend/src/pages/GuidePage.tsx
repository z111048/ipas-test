import { useParams } from 'react-router-dom'
import { useEffect } from 'react'
import s1g from '@data/guide/subject1_guide.json'
import s2g from '@data/guide/subject2_guide.json'
import type { GuideData } from '../types'
import { GUIDE_NOTICES } from '../constants/guideNotices'

const guide1 = s1g as GuideData
const guide2 = s2g as GuideData

export default function GuidePage() {
  const { subjectId, chapterId } = useParams<{ subjectId: string; chapterId: string }>()

  const guide = subjectId === 's1' ? guide1 : guide2
  const chapter = guide?.chapters?.find((c) => c.id === chapterId)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [chapterId])

  if (!guide?.chapters) {
    return (
      <div className="text-error p-4">
        學習指引資料尚未載入，請先執行 parse_guides.py 後重新建置。
      </div>
    )
  }

  if (!chapter) {
    return <div className="text-error p-4">找不到章節：{chapterId}</div>
  }

  const paragraphs = chapter.content.split(/\n{2,}/).filter((p) => p.trim())
  const notice = chapterId ? GUIDE_NOTICES[chapterId] : undefined

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">{chapter.title}</div>
      <div className="text-text-light mb-4">
        {guide.subject} › 學習指引原文（共 {chapter.content.length.toLocaleString()} 字元）
      </div>

      {notice && (
        <div
          className="bg-[#fef9e7] border-l-4 border-warning rounded-lg p-4 mb-4 text-[0.88rem] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: notice }}
        />
      )}

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
            📄 {paragraphs.length} 段落
          </span>
          <span className="text-[0.82rem] bg-[#eef5ff] text-accent px-3 py-1 rounded-full">
            📝 {chapter.content.length.toLocaleString()} 字元
          </span>
        </div>
        <div className="text-[0.82rem] text-text-light font-semibold mb-2">章節重點子主題</div>
        <div className="flex flex-wrap gap-2">
          {chapter.subtopics.map((s) => (
            <span key={s} className="text-[0.82rem] bg-[#e8f4fd] text-accent-hover px-3 py-1 rounded-full border border-accent/20">
              {s}
            </span>
          ))}
        </div>
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5">
        <div className="prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text space-y-4">
          {paragraphs.map((para, i) => (
            <p key={i}>
              {para.split('\n').map((line, j, arr) => (
                <span key={j}>
                  {line}
                  {j < arr.length - 1 && <br />}
                </span>
              ))}
            </p>
          ))}
        </div>
      </div>
    </div>
  )
}
