import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSE } from '../src/hooks/useSSE'

// Mock EventSource
class MockEventSource {
  url: string
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    mockEventSourceInstances.push(this)
  }
}

const mockEventSourceInstances: MockEventSource[] = []

vi.stubGlobal('EventSource', MockEventSource)

describe('useSSE', () => {
  beforeEach(() => {
    mockEventSourceInstances.length = 0
  })

  afterEach(() => {
    mockEventSourceInstances.length = 0
  })

  it('should have correct initial state', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    expect(result.current.data).toBe('')
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('should connect and set loading state', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test message')
    })

    expect(result.current.isLoading).toBe(true)
    expect(mockEventSourceInstances).toHaveLength(1)
    expect(mockEventSourceInstances[0].url).toBe('/api/test?message=test%20message')
  })

  it('should accumulate data on message events', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test')
    })

    const eventSource = mockEventSourceInstances[0]

    // Simulate message events
    act(() => {
      if (eventSource.onmessage) {
        eventSource.onmessage({ data: 'Hello' } as MessageEvent)
      }
    })

    expect(result.current.data).toBe('Hello')

    act(() => {
      if (eventSource.onmessage) {
        eventSource.onmessage({ data: ' World' } as MessageEvent)
      }
    })

    expect(result.current.data).toBe('Hello World')
  })

  it('should handle [DONE] message', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test')
    })

    const eventSource = mockEventSourceInstances[0]

    act(() => {
      if (eventSource.onmessage) {
        eventSource.onmessage({ data: '[DONE]' } as MessageEvent)
      }
    })

    expect(result.current.isLoading).toBe(false)
    expect(eventSource.close).toHaveBeenCalled()
  })

  it('should handle [ERROR] message', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test')
    })

    const eventSource = mockEventSourceInstances[0]

    act(() => {
      if (eventSource.onmessage) {
        eventSource.onmessage({ data: '[ERROR]Something went wrong' } as MessageEvent)
      }
    })

    expect(result.current.error).toBe('Something went wrong')
    expect(result.current.isLoading).toBe(false)
    expect(eventSource.close).toHaveBeenCalled()
  })

  it('should handle connection error', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test')
    })

    const eventSource = mockEventSourceInstances[0]

    act(() => {
      if (eventSource.onerror) {
        eventSource.onerror()
      }
    })

    expect(result.current.error).toBe('Connection error')
    expect(result.current.isLoading).toBe(false)
    expect(eventSource.close).toHaveBeenCalled()
  })

  it('should disconnect manually', () => {
    const { result } = renderHook(() => useSSE('/api/test'))

    act(() => {
      result.current.connect('test')
    })

    const eventSource = mockEventSourceInstances[0]

    act(() => {
      result.current.disconnect()
    })

    expect(eventSource.close).toHaveBeenCalled()
    expect(result.current.isLoading).toBe(false)
  })
})
