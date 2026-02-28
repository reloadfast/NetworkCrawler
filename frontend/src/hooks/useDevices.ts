/**
 * useDevices — fetches the full device list from GET /api/devices
 * useDevice  — fetches a single device by ID from GET /api/devices/:id
 */
import { useEffect, useState } from "react";
import type { Device } from "../types/api";

export interface UseDevicesResult {
  devices: Device[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useDevices(): UseDevicesResult {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch("/api/devices")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Device[]>;
      })
      .then((data) => {
        if (!cancelled) {
          setDevices(data);
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

  return { devices, loading, error, refetch: () => setTick((t) => t + 1) };
}

export interface UseDeviceResult {
  device: Device | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useDevice(id: number): UseDeviceResult {
  const [device, setDevice] = useState<Device | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/devices/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Device>;
      })
      .then((data) => {
        if (!cancelled) {
          setDevice(data);
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
  }, [id, tick]);

  return { device, loading, error, refetch: () => setTick((t) => t + 1) };
}
