import { useEffect } from 'react'
import { useExamStore } from '../store/examStore'

export function useExamTimer(active: boolean) {
  const tickTimer = useExamStore((s) => s.tickTimer)
  const submitExam = useExamStore((s) => s.submitExam)
  const secondsRemaining = useExamStore((s) => s.secondsRemaining)

  useEffect(() => {
    if (!active) return
    const id = setInterval(() => tickTimer(), 1000)
    return () => clearInterval(id)
  }, [active, tickTimer])

  useEffect(() => {
    if (active && secondsRemaining <= 0) submitExam()
  }, [secondsRemaining, active, submitExam])
}
