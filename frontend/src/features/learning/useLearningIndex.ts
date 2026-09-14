import { useCallback, useEffect, useState } from 'react'
import { loadLearningIndex, type LearningIndex } from './data'

export function useLearningIndex() {
  const [index, setIndex] = useState<LearningIndex | null>()
  const [error, setError] = useState<string>()

  const load = useCallback((refresh = false) => {
    setError(undefined)
    setIndex(undefined)
    loadLearningIndex(refresh)
      .then(setIndex)
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
  }, [])

  useEffect(() => load(), [load])
  return { index, error, retry: () => load(true) }
}
