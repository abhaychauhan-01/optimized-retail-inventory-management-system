import { useCallback, useEffect, useState } from 'react'
import { errorMessage } from '../services/api'

interface AsyncResult<T> {
  load: () => Promise<T>
  request: number
  data: T
  error: string
}

export function useAsyncData<T>(load: () => Promise<T>) {
  const [request, setRequest] = useState(0)
  const [result, setResult] = useState<AsyncResult<T> | null>(null)

  useEffect(() => {
    let active = true
    void load()
      .then((value) => {
        if (active) setResult({ load, request, data: value, error: '' })
      })
      .catch((reason: unknown) => {
        if (active) setResult({ load, request, data: null as T, error: errorMessage(reason) })
      })
    return () => { active = false }
  }, [load, request])

  const retry = useCallback(() => {
    setRequest((current) => current + 1)
  }, [])

  const current = result?.load === load && result.request === request ? result : null
  return { data: current?.data ?? null, loading: current === null, error: current?.error ?? '', retry }
}