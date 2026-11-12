import { afterEach, describe, expect, it, vi } from 'vitest'
import { isNetworkError, onReconnect, setOnline, useOnline } from '@/model/online'
import { ApiError } from '@/model/http'

afterEach(() => {
  setOnline(true)
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useOnline', () => {
  it('shares one state between callers', () => {
    const a = useOnline().isOnline
    const b = useOnline().isOnline
    setOnline(false)
    expect(a.value).toBe(false)
    expect(b.value).toBe(false)
  })

  it('tells network failures from answers of the server', () => {
    expect(isNetworkError(new TypeError('Failed to fetch'))).toBe(true)
    expect(isNetworkError(new ApiError(['x'], 500))).toBe(false)
  })

  it('notifies when the connection comes back, once', () => {
    const back = vi.fn<() => void>()
    const stop = onReconnect(back)
    setOnline(false)
    setOnline(true)
    setOnline(true)
    expect(back).toHaveBeenCalledTimes(1)
    stop()
  })

  it('probes the health endpoint while offline and recovers', async () => {
    vi.useFakeTimers()
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError('x'))
      .mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetchMock)
    const { isOnline } = useOnline()
    setOnline(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(isOnline.value).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(fetchMock).toHaveBeenCalledWith('/api/public/health')
    expect(isOnline.value).toBe(true)
  })
})
