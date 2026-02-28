/**
 * Tests for Issue #14 — polish & UX components.
 * Covers: Skeleton/SkeletonCard/SkeletonTable, ScanBanner,
 * ToastContainer/useToast, useScanStatus, and DashboardPage polish.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  Skeleton,
  SkeletonCard,
  SkeletonTable,
} from "../src/components/Skeleton";
import { ScanBanner } from "../src/components/ScanBanner";
import { ToastContainer } from "../src/components/Toast";
import { useToast } from "../src/hooks/useToast";
import { useScanStatus } from "../src/hooks/useScanStatus";
import { DashboardPage } from "../src/pages/DashboardPage";
import type { Scan, Device, RiskSummary } from "../src/types/api";

// ── fixtures ──────────────────────────────────────────────────────────────────

const completedScan: Scan = {
  id: 1,
  status: "completed",
  triggered_by: "manual",
  started_at: "2024-06-01T10:00:00",
  finished_at: "2024-06-01T10:01:00",
  duration_seconds: 60,
  devices_found: 2,
  error_message: null,
};

const runningScan: Scan = {
  id: 2,
  status: "running",
  triggered_by: "manual",
  started_at: "2024-06-01T11:00:00",
  finished_at: null,
  duration_seconds: null,
  devices_found: null,
  error_message: null,
};

const mockDevice: Device = {
  id: 1,
  ip_address: "10.0.0.1",
  mac_address: null,
  vendor: null,
  hostname: "router",
  os_guess: null,
  first_seen: null,
  last_seen: null,
  ports: [],
};

const mockSummary: RiskSummary = {
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
  total: 0,
};

function mockFetch(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  });
}

function buildFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((url: string) => {
    const defaults: Record<string, unknown> = {
      "/api/devices": [mockDevice],
      "/api/scans": [completedScan],
      "/api/risks": [],
      "/api/risks/summary": mockSummary,
      ...overrides,
    };
    const match = Object.keys(defaults).find(
      (k) => url === k || url.startsWith(k + "?"),
    );
    const data = match !== undefined ? defaults[match] : [];
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(data),
    });
  });
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

// ── Skeleton ──────────────────────────────────────────────────────────────────

describe("Skeleton", () => {
  it("renders the correct number of rows", () => {
    const { container } = render(<Skeleton rows={4} />);
    // Each row is a div[aria-hidden="true"] inside the status container
    const rows = container.querySelectorAll('[aria-hidden="true"]');
    expect(rows).toHaveLength(4);
  });

  it('has aria-label "Loading" and role="status"', () => {
    render(<Skeleton />);
    expect(
      screen.getByRole("status", { name: /loading/i }),
    ).toBeInTheDocument();
  });

  it("defaults to 3 rows", () => {
    const { container } = render(<Skeleton />);
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(3);
  });
});

describe("SkeletonCard", () => {
  it("renders a single status region with aria-label Loading", () => {
    render(<SkeletonCard />);
    expect(
      screen.getByRole("status", { name: /loading/i }),
    ).toBeInTheDocument();
  });
});

describe("SkeletonTable", () => {
  it("renders header + body rows", () => {
    const { container } = render(<SkeletonTable rows={3} />);
    // header row + 3 body rows = 4 aria-hidden elements
    const hidden = container.querySelectorAll('[aria-hidden="true"]');
    expect(hidden).toHaveLength(4);
  });

  it("has accessible loading label", () => {
    render(<SkeletonTable />);
    expect(
      screen.getByRole("status", { name: /loading/i }),
    ).toBeInTheDocument();
  });
});

// ── ScanBanner ────────────────────────────────────────────────────────────────

describe("ScanBanner", () => {
  it("renders with accessible role and label", () => {
    render(<ScanBanner />);
    expect(
      screen.getByRole("status", { name: /scan in progress/i }),
    ).toBeInTheDocument();
  });

  it('shows "Scan in progress" text', () => {
    render(<ScanBanner />);
    expect(screen.getByText(/Scan in progress/i)).toBeInTheDocument();
  });

  it("shows scan ID when provided", () => {
    render(<ScanBanner scanId={42} />);
    expect(screen.getByText(/#42/)).toBeInTheDocument();
  });

  it("does not show scan ID when null", () => {
    render(<ScanBanner scanId={null} />);
    expect(screen.queryByText(/#\d+/)).not.toBeInTheDocument();
  });
});

// ── ToastContainer / useToast ─────────────────────────────────────────────────

describe("ToastContainer", () => {
  it("renders nothing when toasts is empty", () => {
    const { container } = render(
      <ToastContainer toasts={[]} onDismiss={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders a toast message", () => {
    const toasts = [
      { id: "1", message: "Scan completed!", variant: "success" as const },
    ];
    render(<ToastContainer toasts={toasts} onDismiss={() => {}} />);
    expect(screen.getByText("Scan completed!")).toBeInTheDocument();
  });

  it("calls onDismiss when dismiss button clicked", () => {
    const onDismiss = vi.fn();
    const toasts = [
      { id: "abc", message: "Test toast", variant: "info" as const },
    ];
    render(<ToastContainer toasts={toasts} onDismiss={onDismiss} />);
    fireEvent.click(
      screen.getByRole("button", { name: /dismiss notification/i }),
    );
    expect(onDismiss).toHaveBeenCalledWith("abc");
  });

  it('toast has role="alert"', () => {
    const toasts = [{ id: "2", message: "Hello", variant: "error" as const }];
    render(<ToastContainer toasts={toasts} onDismiss={() => {}} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("useToast", () => {
  it("starts with no toasts", () => {
    const { result } = renderHook(() => useToast());
    expect(result.current.toasts).toHaveLength(0);
  });

  it("addToast adds a toast with the given message and variant", () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.addToast("Scan started", "success");
    });
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe("Scan started");
    expect(result.current.toasts[0].variant).toBe("success");
  });

  it("dismissToast removes the toast by id", () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.addToast("Hello", "info");
    });
    const id = result.current.toasts[0].id;
    act(() => {
      result.current.dismissToast(id);
    });
    expect(result.current.toasts).toHaveLength(0);
  });

  it('defaults variant to "info" when not specified', () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.addToast("No variant");
    });
    expect(result.current.toasts[0].variant).toBe("info");
  });
});

// ── useScanStatus ─────────────────────────────────────────────────────────────

describe("useScanStatus", () => {
  it("returns loading=true initially", () => {
    vi.stubGlobal("fetch", mockFetch([completedScan]));
    const { result } = renderHook(() => useScanStatus());
    expect(result.current.loading).toBe(true);
  });

  it("returns latestScan and isRunning=false for a completed scan", async () => {
    vi.stubGlobal("fetch", mockFetch([completedScan]));
    const { result } = renderHook(() => useScanStatus(60_000));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.latestScan?.id).toBe(1);
    expect(result.current.isRunning).toBe(false);
  });

  it('returns isRunning=true when scan status is "running"', async () => {
    vi.stubGlobal("fetch", mockFetch([runningScan]));
    const { result } = renderHook(() => useScanStatus(60_000));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isRunning).toBe(true);
  });

  it("returns null latestScan when scans list is empty", async () => {
    vi.stubGlobal("fetch", mockFetch([]));
    const { result } = renderHook(() => useScanStatus(60_000));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.latestScan).toBeNull();
    expect(result.current.isRunning).toBe(false);
  });

  it("handles fetch failure gracefully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error")),
    );
    const { result } = renderHook(() => useScanStatus(60_000));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.latestScan).toBeNull();
    expect(result.current.isRunning).toBe(false);
  });
});

// ── DashboardPage polish ──────────────────────────────────────────────────────

describe("DashboardPage (polish)", () => {
  it("shows scan button enabled when no scan is running", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /trigger a new scan/i }),
      ).not.toBeDisabled(),
    );
  });

  it("disables scan button when a scan is running", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/scans": [runningScan] }));
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    // Button should be disabled when scan is running
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /scan in progress/i }),
      ).toBeDisabled(),
    );
  });

  it("shows ScanBanner when scan is running", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/scans": [runningScan] }));
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("status", { name: /scan in progress/i }),
      ).toBeInTheDocument(),
    );
  });

  it("does not show ScanBanner when no scan is running", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Dashboard")).toBeInTheDocument(),
    );
    // Wait for data to load and confirm banner is absent
    await waitFor(() =>
      expect(screen.getByText("Total Devices")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("status", { name: /scan in progress/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a toast after triggering a scan", async () => {
    const fetchMock = buildFetch();
    // Override trigger endpoint
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/scans/trigger") {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ scan_id: 99 }),
        });
      }
      const defaults: Record<string, unknown> = {
        "/api/devices": [mockDevice],
        "/api/scans": [completedScan],
        "/api/risks": [],
        "/api/risks/summary": mockSummary,
      };
      const match = Object.keys(defaults).find(
        (k) => url === k || url.startsWith(k + "?"),
      );
      const data = match !== undefined ? defaults[match] : [];
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(data),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    // Wait until button is enabled
    const btn = await screen.findByRole("button", {
      name: /trigger a new scan/i,
    });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(screen.getByText(/Scan #99 started/i)).toBeInTheDocument(),
    );
  });
});
