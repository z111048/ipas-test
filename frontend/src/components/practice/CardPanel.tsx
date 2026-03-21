import type { QuestionCard } from '../../types'
import FreqBar from './FreqBar'

interface CardPanelProps {
  card: QuestionCard
}

export default function CardPanel({ card }: CardPanelProps) {
  return (
    <div className="mt-3 border border-border rounded-xl overflow-hidden">
      <div className="bg-primary text-white text-[0.82rem] font-semibold px-4 py-2">解說圖卡</div>
      <div className="p-4 space-y-3">
        {[
          { icon: '📌', label: '核心概念', value: card.concept },
          { icon: '🔑', label: '記憶口訣', value: card.mnemonic },
          { icon: '⚠️', label: '常見混淆', value: card.confusion },
        ].map(({ icon, label, value }) => (
          <div key={label} className="flex gap-3 text-[0.88rem]">
            <span className="w-5 shrink-0">{icon}</span>
            <span className="text-text-light w-16 shrink-0">{label}</span>
            <span className="text-app-text">{value}</span>
          </div>
        ))}
        <div className="flex gap-3 text-[0.88rem] items-center">
          <span className="w-5 shrink-0">📊</span>
          <span className="text-text-light w-16 shrink-0">出題頻率</span>
          <FreqBar frequency={card.frequency} />
        </div>
      </div>
    </div>
  )
}
