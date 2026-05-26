import type { QuestionCard } from '../../types'
import FreqBar from './FreqBar'

interface CardPanelProps {
  card: QuestionCard
}

export default function CardPanel({ card }: CardPanelProps) {
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
        <div className="flex gap-3 text-[0.88rem] items-center">
          <span className="w-6 shrink-0 text-[0.72rem] font-bold text-accent">04</span>
          <span className="text-text-light w-16 shrink-0">出題頻率</span>
          <FreqBar frequency={card.frequency} />
        </div>
      </div>
    </div>
  )
}
