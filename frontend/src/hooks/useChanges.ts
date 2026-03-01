import { useCallback, useEffect, useState } from "react";
import type { ChangesSummary, ScanEvent } from "../types/api";

export interface UseChangesOptions {
  reviewed?: boolean;
  device_id?: number;
  limit?: number;
}

export interface UseChangesResult {
  events: ScanEvent[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  markReviewed: (id: number) => Promise<void>;
  markAllReviewed: () => Promise<void>;
}

export function useChanges(opts: UseChangesOptions = {}): UseChangesResult {
  const { reviewed, device_id, limit = 200 } = opts;
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = useCallback(() => {
    const params = new URLSearchParams();
    if (reviewed !== undefined) params.set("reviewed", String(reviewed));
    if (device_id !== undefined) params.set("device_id", String(device_id));
    params.set("limit", String(limit));

    setLoading(true);
    fetch(`/api/changes?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ScanEvent[]>;
      })
      .then(setEvents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [reviewed, device_id, limit]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const markReviewed = async (id: number) => {
    await fetch(`/api/changes/${id}/reviewed`, { method: "PATCH" });
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, reviewed: true } : e)),
    );
  };

  const markAllReviewed = async () => {
    await fetch("/api/changes/reviewed/all", { method: "PATCH" });
    setEvents((prev) => prev.map((e) => ({ ...e, reviewed: true })));
  };

  return {
    events,
    loading,
    error,
    refetch: fetchEvents,
    markReviewed,
    markAllReviewed,
  };
}

export interface UseChangesSummaryResult {
  unreviewed: number;
}

export function useChangesSummary(): UseChangesSummaryResult {
  const [unreviewed, setUnreviewed] = useState(0);

  useEffect(() => {
    const fetchSummary = () => {
      fetch("/api/changes/summary")
        .then((r) => r.json() as Promise<ChangesSummary>)
        .then((d) => setUnreviewed(d.unreviewed))
        .catch(() => {});
    };
    fetchSummary();
    const interval = setInterval(fetchSummary, 30_000);
    return () => clearInterval(interval);
  }, []);

  return { unreviewed };
}
