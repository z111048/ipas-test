interface StatBoxProps {
  value: number | string
  label: string
  valueColor?: string
}

export default function StatBox({ value, label, valueColor }: StatBoxProps) {
  return (
    <div className="bg-card rounded-xl p-5 text-center shadow-sm border border-border flex-1 min-w-[100px]">
      <div className={`text-3xl font-bold ${valueColor ?? 'text-primary'}`}>{value}</div>
      <div className="text-[0.82rem] text-text-light mt-1">{label}</div>
    </div>
  )
}
