import { useParams } from 'react-router-dom'
import { useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
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

  const isMarkdown = chapter.content_format === 'markdown' || chapter.content?.trimStart().startsWith('#') || chapter.content?.trimStart().startsWith('##')
  const paragraphs = isMarkdown ? [] : chapter.content.split(/\n{2,}/).filter((p) => p.trim())
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
        {isMarkdown ? (
          <div className="prose prose-sm max-w-none text-[0.9rem] leading-8 text-app-text">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h2: ({ children }) => (
                <h2 className="text-lg font-bold text-primary mt-6 mb-2 border-b border-border pb-1">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-semibold text-accent mt-4 mb-1">{children}</h3>
              ),
              p: ({ children }) => (
                <p className="mb-3 leading-8">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="list-disc list-outside pl-5 mb-3 space-y-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-outside pl-5 mb-3 space-y-1">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="leading-7">{children}</li>
              ),
              table: ({ children }) => (
                <div className="overflow-x-auto my-4">
                  <table className="border-collapse w-full text-sm">{children}</table>
                </div>
              ),
              th: ({ children }) => (
                <th className="border border-border bg-[#eef5ff] text-accent px-3 py-2 text-left font-semibold">{children}</th>
              ),
              td: ({ children }) => (
                <td className="border border-border px-3 py-2 leading-6">{children}</td>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-app-text">{children}</strong>
              ),
            }}
          >
            {chapter.content}
          </ReactMarkdown>
          </div>
        ) : (
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
        )}
      </div>
    </div>
  )
}
