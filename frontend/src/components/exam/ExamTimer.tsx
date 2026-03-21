import { useExamStore } from '../../store/examStore'

export default function ExamTimer() {
  const seconds = useExamStore((s) => s.secondsRemaining)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  const display = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`

  const colorClass =
    seconds <= 300
      ? 'text-error'
      : seconds <= 600
        ? 'text-warning'
        : 'text-white'

  return (
    <div className={`text-3xl font-bold tabular-nums ${colorClass}`}>{display}</div>
  )
}
