/**
 * useAppVersion — fetches the application version from GET /health.
 *
 * Uses a simple fetch with no re-fetch after the first successful load
 * (version is immutable for the lifetime of a container). Falls back to
 * null while loading and on error.
 */
import { useEffect, useState } from 'react'
import type { HealthResponse } from '../types/api'

export interface UseAppVersionResult {
  version: string | null
  loading: boolean
}

export function useAppVersion(): UseAppVersionResult {
  const [version, setVersion] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: HealthResponse) => {
        if (!cancelled) {
          setVersion(data.version ?? null)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, []) // empty deps — fetch once on mount

  return { version, loading }
}
