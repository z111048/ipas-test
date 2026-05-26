interface StatBoxProps {
  value: number | string
  label: string
  valueColor?: string
}

export default function StatBox({ value, label, valueColor }: StatBoxProps) {
  return (
    <div className="surface-compact p-4 text-center flex-1 min-w-[112px]">
      <div className={`text-2xl font-bold tabular-nums ${valueColor ?? 'text-primary'}`}>{value}</div>
      <div className="text-[0.82rem] text-text-light mt-1">{label}</div>
    </div>
  )
}
