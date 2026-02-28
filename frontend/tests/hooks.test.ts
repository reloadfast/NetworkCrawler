/**
 * Tests for useDevices, useDevice, useScans, useRisks, useRiskSummary hooks.
 * All tests mock fetch via vi.stubGlobal.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useDevices, useDevice } from "../src/hooks/useDevices";
import { useScans } from "../src/hooks/useScans";
import { useRisks, useRiskSummary } from "../src/hooks/useRisks";
import type { Device, Scan, Risk, RiskSummary } from "../src/types/api";

const mockDevice: Device = {
  id: 1,
  ip_address: "192.168.1.1",
  mac_address: "aa:bb:cc:dd:ee:ff",
  vendor: "Acme",
  hostname: "router",
  os_guess: "Linux",
  first_seen: "2024-01-01T00:00:00",
  last_seen: "2024-01-02T00:00:00",
  ports: [
    {
      id: 10,
      port_number: 80,
      protocol: "tcp",
      service_name: "http",
      version_banner: null,
    },
  ],
};

const mockScan: Scan = {
  id: 1,
  status: "completed",
  triggered_by: "manual",
  started_at: "2024-01-01T00:00:00",
  finished_at: "2024-01-01T00:01:00",
  duration_seconds: 60,
  devices_found: 5,
  error_message: null,
};

const mockRisk: Risk = {
  id: 1,
  device_id: 1,
  severity: "high",
  check_id: "open_telnet",
  title: "Telnet open",
  description: "Port 23 is open",
  detected_at: "2024-01-01T00:00:00",
};

const mockSummary: RiskSummary = {
  critical: 1,
  high: 2,
  medium: 3,
  low: 4,
  total: 10,
};

function mockFetch(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  });
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

// ── useDevices ─────────────────────────────────────────────────────────────────

describe("useDevices", () => {
  it("returns devices on success", async () => {
    vi.stubGlobal("fetch", mockFetch([mockDevice]));
    const { result } = renderHook(() => useDevices());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.devices).toHaveLength(1);
    expect(result.current.devices[0].ip_address).toBe("192.168.1.1");
    expect(result.current.error).toBeNull();
  });

  it("sets error on HTTP failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    const { result } = renderHook(() => useDevices());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toMatch(/HTTP 500/);
    expect(result.current.devices).toHaveLength(0);
  });

  it("refetch increments tick and re-fetches", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([mockDevice]),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDevices());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    result.current.refetch();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});

// ── useDevice ─────────────────────────────────────────────────────────────────

describe("useDevice", () => {
  it("fetches single device by id", async () => {
    vi.stubGlobal("fetch", mockFetch(mockDevice));
    const { result } = renderHook(() => useDevice(1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.device?.id).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("sets error on 404", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    const { result } = renderHook(() => useDevice(99));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeTruthy();
    expect(result.current.device).toBeNull();
  });
});

// ── useScans ─────────────────────────────────────────────────────────────────

describe("useScans", () => {
  it("returns scans on success", async () => {
    vi.stubGlobal("fetch", mockFetch([mockScan]));
    const { result } = renderHook(() => useScans());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.scans).toHaveLength(1);
    expect(result.current.scans[0].status).toBe("completed");
  });

  it("sets error on network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error")),
    );
    const { result } = renderHook(() => useScans());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Network error");
  });
});

// ── useRisks ──────────────────────────────────────────────────────────────────

describe("useRisks", () => {
  it("returns risks on success", async () => {
    vi.stubGlobal("fetch", mockFetch([mockRisk]));
    const { result } = renderHook(() => useRisks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.risks).toHaveLength(1);
    expect(result.current.risks[0].severity).toBe("high");
  });

  it("appends severity filter to query string", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRisks({ severity: "critical" }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("severity=critical");
  });

  it("appends device_id filter to query string", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRisks({ deviceId: 42 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("device_id=42");
  });

  it("fetches without query string when no filters", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRisks());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/api/risks");
  });
});

// ── useRiskSummary ────────────────────────────────────────────────────────────

describe("useRiskSummary", () => {
  it("returns summary on success", async () => {
    vi.stubGlobal("fetch", mockFetch(mockSummary));
    const { result } = renderHook(() => useRiskSummary());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.summary?.total).toBe(10);
    expect(result.current.summary?.critical).toBe(1);
  });

  it("sets error on failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    const { result } = renderHook(() => useRiskSummary());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeTruthy();
    expect(result.current.summary).toBeNull();
  });
});
