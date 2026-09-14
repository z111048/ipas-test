import { useCallback, useEffect, useState } from 'react'
import { loadLearningItem, type LearningItem, type LearningKind } from './data'

export function useLearningItem<T extends object>(kind: LearningKind, path?: string) {
  const [item, setItem] = useState<LearningItem<T>>()
  const [error, setError] = useState<string>()
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let active = true
    setItem(undefined)
    setError(undefined)
    if (!path) return
    loadLearningItem(path)
      .then((loaded) => {
        if (!active) return
        if (loaded.kind !== kind) throw new Error('學習內容類型不符')
        setItem(loaded as LearningItem<T>)
      })
      .catch((reason) => active && setError(reason instanceof Error ? reason.message : String(reason)))
    return () => { active = false }
  }, [kind, path, nonce])

  return { item, error, retry: useCallback(() => setNonce((value) => value + 1), []) }
}
