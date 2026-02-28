/**
 * useRisks      — fetches risks list from GET /api/risks with optional filters
 * useRiskSummary — fetches risk counts per severity from GET /api/risks/summary
 */
import { useEffect, useState } from "react";
import type { Risk, RiskSummary, Severity } from "../types/api";

export interface UseRisksOptions {
  severity?: Severity;
  deviceId?: number;
}

export interface UseRisksResult {
  risks: Risk[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useRisks(options: UseRisksOptions = {}): UseRisksResult {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const { severity, deviceId } = options;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (severity) params.set("severity", severity);
    if (deviceId !== undefined) params.set("device_id", String(deviceId));
    const qs = params.toString();
    fetch(`/api/risks${qs ? `?${qs}` : ""}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Risk[]>;
      })
      .then((data) => {
        if (!cancelled) {
          setRisks(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [severity, deviceId, tick]);

  return { risks, loading, error, refetch: () => setTick((t) => t + 1) };
}

export interface UseRiskSummaryResult {
  summary: RiskSummary | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useRiskSummary(): UseRiskSummaryResult {
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch("/api/risks/summary")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<RiskSummary>;
      })
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { summary, loading, error, refetch: () => setTick((t) => t + 1) };
}
