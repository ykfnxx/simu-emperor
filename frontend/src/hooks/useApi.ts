import { useState, useCallback } from 'react'
import { api, ApiError } from '../api/client'

interface UseApiReturn<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  execute: (...args: unknown[]) => Promise<T | null>
  reset: () => void
}

export function useApi<T>(
  apiFn: (...args: unknown[]) => Promise<T>
): UseApiReturn<T> {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const execute = useCallback(
    async (...args: unknown[]): Promise<T | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const result = await apiFn(...args)
        setData(result)
        setIsLoading(false)
        return result
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.data.detail || err.data.error
            : err instanceof Error
              ? err.message
              : 'An error occurred'
        setError(message)
        setIsLoading(false)
        return null
      }
    },
    [apiFn]
  )

  const reset = useCallback(() => {
    setData(null)
    setError(null)
    setIsLoading(false)
  }, [])

  return { data, isLoading, error, execute, reset }
}

// Pre-configured hooks
export function useGameState() {
  return useApi(api.getState)
}

export function useAdvanceTurn() {
  return useApi(api.advanceTurn)
}

export function useAgents() {
  return useApi(api.getAgents)
}

export function useReports() {
  return useApi(api.getReports)
}
