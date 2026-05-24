import { useEffect } from 'react'
import { useExamStore } from '../store/examStore'

export function useExamTimer(active: boolean) {
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => {
      const { secondsRemaining, submitExam, tickTimer } = useExamStore.getState()
      if (secondsRemaining <= 1) {
        submitExam()
        return
      }
      tickTimer()
    }, 1000)
    return () => clearInterval(id)
  }, [active])
}
