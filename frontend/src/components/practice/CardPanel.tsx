import { useEffect, useState } from 'react'
import type { QuestionCard } from '../../types'
import { loadChapterExamStat, type ChapterExamStat } from '../../data/chapterExamStats'

interface CardPanelProps {
  card: QuestionCard
  /** 用來查該章的考題統計（第四格）；查不到就不顯示那一格 */
  questionId?: string
}

export default function CardPanel({ card, questionId }: CardPanelProps) {
  const [stat, setStat] = useState<ChapterExamStat | null>(null)

  useEffect(() => {
    if (!questionId) return
    let active = true
    loadChapterExamStat(questionId).then((loaded) => {
      if (active) setStat(loaded)
    })
    return () => {
      active = false
    }
  }, [questionId])

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border bg-white">
      <div className="border-b border-border bg-[#f8fafc] px-4 py-2 text-[0.8rem] font-semibold text-primary">解說圖卡</div>
      <div className="p-4 space-y-3">
        {[
          { icon: '01', label: '核心概念', value: card.concept },
          { icon: '02', label: '記憶口訣', value: card.mnemonic },
          { icon: '03', label: '常見混淆', value: card.confusion },
        ].map(({ icon, label, value }) => (
          <div key={label} className="flex gap-3 text-[0.88rem]">
            <span className="w-6 shrink-0 text-[0.72rem] font-bold text-accent">{icon}</span>
            <span className="text-text-light w-16 shrink-0">{label}</span>
            <span className="text-app-text content-justify">{value}</span>
          </div>
        ))}
        {stat && (
          <div className="flex gap-3 text-[0.88rem]">
            <span className="w-6 shrink-0 text-[0.72rem] font-bold text-accent">04</span>
            <span className="text-text-light w-16 shrink-0">章節考頻</span>
            <span className="text-app-text">
              本章歷屆公告試題出現 <strong className="tabular-nums">{stat.questions}</strong> 題
              <span className="text-text-light">
                （{stat.subject}第 {stat.rank} 熱，共 {stat.total} 章）
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
