/**
 * useRecommendations — fetches recommendations from GET /api/recommendations
 *                      with optional device_id and severity filters
 * useDeviceRecommendations — fetches recommendations for a specific device
 *                             from GET /api/devices/{id}/recommendations
 */
import { useEffect, useState } from 'react'
import type { Recommendation, Severity } from '../types/api'

export interface UseRecommendationsOptions {
  deviceId?: number
  severity?: Severity
}

export interface UseRecommendationsResult {
  recommendations: Recommendation[]
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useRecommendations(
  options: UseRecommendationsOptions = {},
): UseRecommendationsResult {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const { deviceId, severity } = options

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const params = new URLSearchParams()
    if (deviceId !== undefined) params.set('device_id', String(deviceId))
    if (severity) params.set('severity', severity)
    const qs = params.toString()
    fetch(`/api/recommendations${qs ? `?${qs}` : ''}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Recommendation[]>
      })
      .then((data) => {
        if (!cancelled) {
          setRecommendations(data)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [deviceId, severity, tick])

  return {
    recommendations,
    loading,
    error,
    refetch: () => setTick((t) => t + 1),
  }
}

export interface UseDeviceRecommendationsResult {
  recommendations: Recommendation[]
  loading: boolean
  error: string | null
}

export function useDeviceRecommendations(deviceId: number): UseDeviceRecommendationsResult {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(`/api/devices/${deviceId}/recommendations`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Recommendation[]>
      })
      .then((data) => {
        if (!cancelled) {
          setRecommendations(data)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [deviceId])

  return { recommendations, loading, error }
}
