import { useEffect } from 'react'
import { useExamStore } from '../store/examStore'

export function useExamTimer(active: boolean) {
  useEffect(() => {
    if (!active) return

    const sync = () => useExamStore.getState().syncTimer()
    sync()
    const id = window.setInterval(sync, 1000)
    document.addEventListener('visibilitychange', sync)
    window.addEventListener('focus', sync)
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', sync)
      window.removeEventListener('focus', sync)
    }
  }, [active])
}
