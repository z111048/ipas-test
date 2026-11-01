interface ProgressBarProps {
  percent: number
  color?: string
  height?: string
}

export default function ProgressBar({ percent, color, height = 'h-2' }: ProgressBarProps) {
  return (
    <div className={`w-full bg-border rounded-full overflow-hidden ${height}`}>
      <div
        className={`h-full rounded-full transition-all duration-300 ${color ?? 'bg-accent'}`}
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  )
}
