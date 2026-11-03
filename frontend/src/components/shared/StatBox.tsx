interface StatBoxProps {
  value: number | string
  label: string
  valueColor?: string
  /** muted：放在卡片內時用淡灰底分區，不再套邊框。 */
  tone?: 'card' | 'muted'
}

export default function StatBox({ value, label, valueColor, tone = 'card' }: StatBoxProps) {
  return (
    <div className={`${tone === 'muted' ? 'panel-muted' : 'surface-compact'} p-4 text-center flex-1 min-w-[112px]`}>
      <div className={`text-2xl font-bold tabular-nums ${valueColor ?? 'text-primary'}`}>{value}</div>
      <div className="text-meta text-text-light mt-1">{label}</div>
    </div>
  )
}
