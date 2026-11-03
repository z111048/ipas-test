import { useEffect, useMemo, useState } from 'react'
import { useExamStore } from '../../store/examStore'

interface ExamTimerProps {
  compact?: boolean
}

function statusText(seconds: number) {
  if (seconds <= 60) return '最後 1 分鐘'
  if (seconds <= 300) return '最後 5 分鐘'
  if (seconds <= 600) return '最後 10 分鐘'
  return '時間充足'
}

function announcementBucket(seconds: number) {
  if (seconds <= 60) return Math.ceil(seconds / 15) * 15
  if (seconds <= 300) return Math.ceil(seconds / 30) * 30
  return Math.ceil(seconds / 60) * 60
}

function announcementText(seconds: number) {
  if (seconds <= 0) return '作答時間已到，正在繳卷。'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (remainingSeconds === 0) return `剩餘 ${minutes} 分鐘。`
  if (minutes === 0) return `剩餘 ${remainingSeconds} 秒。`
  return `剩餘 ${minutes} 分 ${remainingSeconds} 秒。`
}

export default function ExamTimer({ compact = false }: ExamTimerProps) {
  const seconds = useExamStore((s) => s.secondsRemaining)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  const display = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  const bucket = useMemo(() => announcementBucket(seconds), [seconds])
  const [liveText, setLiveText] = useState(() => announcementText(bucket))

  // 計時列是白底：警示色 warning #b45309（5.0:1）、wrong #b91c1c（6.5:1）
  const colorClass =
    seconds <= 300
      ? 'text-wrong'
      : seconds <= 600
        ? 'text-warning'
        : 'text-primary'

  useEffect(() => {
    setLiveText(announcementText(bucket))
  }, [bucket])

  const status = statusText(seconds)

  if (compact) {
    return (
      <div className="min-w-0">
        {/* tests/test_exam_flow.py 以 div.text-xl.tabular-nums 的文字比對倒數，內層不要加其他字。 */}
        <div className={`text-xl font-bold tabular-nums leading-none ${colorClass}`}>{display}</div>
        {/* 手機上計時列只留一行，狀態字樣在 sm 以上才顯示。 */}
        <div className="mt-1 hidden text-caption text-text-light sm:block">{status}</div>
        <div aria-live="polite" aria-atomic="true" className="sr-only">{liveText}</div>
      </div>
    )
  }

  return (
    <div>
      <div className={`text-3xl font-bold tabular-nums ${colorClass}`}>{display}</div>
      <div className="mt-1 text-meta font-medium text-text-light">{status}</div>
      <div aria-live="polite" aria-atomic="true" className="sr-only">{liveText}</div>
    </div>
  )
}
