/**
 * useScanStatus — fetches GET /api/scans on mount, then fast-polls every
 * `intervalMs` ms ONLY while a scan is running (status === 'running').
 * When no scan is running it falls back to a slow refresh every 30 s so
 * the UI stays eventually-consistent without hammering the API.
 */
import { useEffect, useRef, useState } from "react";
import type { Scan } from "../types/api";

export interface UseScanStatusResult {
  latestScan: Scan | null;
  isRunning: boolean;
  loading: boolean;
}

const RUNNING_STATUS = new Set(["running", "pending", "in_progress"]);
const IDLE_INTERVAL_MS = 30_000;

export function useScanStatus(intervalMs = 3000): UseScanStatusResult {
  const [latestScan, setLatestScan] = useState<Scan | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isRunningRef = useRef(false);

  const fetchScans = (silent = false) => {
    if (!silent) setLoading(true);
    fetch("/api/scans")
      .then((r) =>
        r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
      )
      .then((data: Scan[]) => {
        const latest = data[0] ?? null;
        setLatestScan(latest);
        setLoading(false);

        const nowRunning = latest !== null && RUNNING_STATUS.has(latest.status);
        // Reschedule interval only when running-state changes
        if (nowRunning !== isRunningRef.current) {
          isRunningRef.current = nowRunning;
          if (intervalRef.current !== null) clearInterval(intervalRef.current);
          intervalRef.current = setInterval(
            () => fetchScans(true),
            nowRunning ? intervalMs : IDLE_INTERVAL_MS,
          );
        }
      })
      .catch(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchScans();
    // Start with idle interval; fetchScans will upgrade to fast-poll if running
    intervalRef.current = setInterval(() => fetchScans(true), IDLE_INTERVAL_MS);

    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, [intervalMs]); // eslint-disable-line react-hooks/exhaustive-deps -- fetchScans is stable

  const isRunning =
    latestScan !== null && RUNNING_STATUS.has(latestScan.status);

  return { latestScan, isRunning, loading };
}
