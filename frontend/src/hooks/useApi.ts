import { useState, useCallback } from 'react'
import { api, ApiError } from '../api/client'
import type { StateResponse, AdvanceResponse, Agent, ReportResponse } from '../types'

interface UseApiReturn<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  reset: () => void
}

interface UseApiExecuteReturn<T> extends UseApiReturn<T> {
  execute: () => Promise<T | null>
}

interface UseApiExecuteWithArgReturn<T, A> extends UseApiReturn<T> {
  execute: (arg: A) => Promise<T | null>
}

function createApiHook<T>(
  apiFn: () => Promise<T>
): () => UseApiExecuteReturn<T> {
  return () => {
    const [data, setData] = useState<T | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const execute = useCallback(async (): Promise<T | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const result = await apiFn()
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
    }, [])

    const reset = useCallback(() => {
      setData(null)
      setError(null)
      setIsLoading(false)
    }, [])

    return { data, isLoading, error, execute, reset }
  }
}

function createApiHookWithArg<T, A>(
  apiFn: (arg: A) => Promise<T>
): () => UseApiExecuteWithArgReturn<T, A> {
  return () => {
    const [data, setData] = useState<T | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const execute = useCallback(async (arg: A): Promise<T | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const result = await apiFn(arg)
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
    }, [])

    const reset = useCallback(() => {
      setData(null)
      setError(null)
      setIsLoading(false)
    }, [])

    return { data, isLoading, error, execute, reset }
  }
}

// Pre-configured hooks
export const useGameState = createApiHook<StateResponse>(api.getState)
export const useAdvanceTurn = createApiHook<AdvanceResponse>(api.advanceTurn)
export const useAgents = createApiHook<Agent[]>(api.getAgents)
export const useReports = createApiHookWithArg<ReportResponse[], number | undefined>(api.getReports)
