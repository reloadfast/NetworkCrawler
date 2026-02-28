/**
 * useScanStatus — polls GET /api/scans every `intervalMs` ms while a scan
 * is running (status === 'running').  Returns the latest scan and whether
 * a scan is currently in progress.
 */
import { useEffect, useRef, useState } from 'react'
import type { Scan } from '../types/api'

export interface UseScanStatusResult {
  latestScan: Scan | null
  isRunning: boolean
  loading: boolean
}

const RUNNING_STATUS = new Set(['running', 'pending', 'in_progress'])

export function useScanStatus(intervalMs = 3000): UseScanStatusResult {
  const [latestScan, setLatestScan] = useState<Scan | null>(null)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchScans = (silent = false) => {
    if (!silent) setLoading(true)
    fetch('/api/scans')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Scan[]) => {
        const latest = data[0] ?? null
        setLatestScan(latest)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchScans()

    intervalRef.current = setInterval(() => {
      // Always poll; only matters visually when running
      fetchScans(true)
    }, intervalMs)

    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current)
    }
  }, [intervalMs])

  const isRunning = latestScan !== null && RUNNING_STATUS.has(latestScan.status)

  return { latestScan, isRunning, loading }
}
