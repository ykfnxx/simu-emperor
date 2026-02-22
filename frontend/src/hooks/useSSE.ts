import { useEffect, useState, useRef, useCallback } from 'react'

interface UseSSEReturn {
  data: string
  isLoading: boolean
  error: string | null
  connect: (message: string) => void
  disconnect: () => void
}

export function useSSE(url: string): UseSSEReturn {
  const [data, setData] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsLoading(false)
  }, [])

  const connect = useCallback(
    (message: string) => {
      // Clean up any existing connection
      disconnect()

      setIsLoading(true)
      setData('')
      setError(null)

      const urlWithParams = `${url}?message=${encodeURIComponent(message)}`
      const eventSource = new EventSource(urlWithParams)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (e) => {
        if (e.data === '[DONE]') {
          setIsLoading(false)
          eventSource.close()
          eventSourceRef.current = null
        } else if (e.data.startsWith('[ERROR]')) {
          setError(e.data.slice(7))
          setIsLoading(false)
          eventSource.close()
          eventSourceRef.current = null
        } else {
          setData((prev) => prev + e.data)
        }
      }

      eventSource.onerror = () => {
        setError('Connection error')
        setIsLoading(false)
        eventSource.close()
        eventSourceRef.current = null
      }
    },
    [url, disconnect]
  )

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return { data, isLoading, error, connect, disconnect }
}
