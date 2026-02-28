/**
 * useScans      — fetches scan history from GET /api/scans
 * useTriggerScan — POSTs to /api/scans/trigger to kick off a new scan
 */
import { useEffect, useState } from 'react'
import type { Scan, TriggerResponse } from '../types/api'

export interface UseScansResult {
  scans: Scan[]
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useScans(): UseScansResult {
  const [scans, setScans] = useState<Scan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch('/api/scans')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Scan[]>
      })
      .then((data) => {
        if (!cancelled) {
          setScans(data)
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
  }, [tick])

  return { scans, loading, error, refetch: () => setTick((t) => t + 1) }
}

export interface UseTriggerScanResult {
  trigger: () => Promise<TriggerResponse | null>
  loading: boolean
  error: string | null
}

export function useTriggerScan(): UseTriggerScanResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const trigger = async (): Promise<TriggerResponse | null> => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/scans/trigger', { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = (await r.json()) as TriggerResponse
      return data
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return null
    } finally {
      setLoading(false)
    }
  }

  return { trigger, loading, error }
}
