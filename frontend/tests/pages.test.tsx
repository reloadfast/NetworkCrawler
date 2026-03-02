/**
 * Integration tests for page components — Dashboard, Devices, DeviceDetail, Risks.
 * All API calls are mocked via vi.stubGlobal('fetch', ...).
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DashboardPage } from "../src/pages/DashboardPage";
import { DevicesPage } from "../src/pages/DevicesPage";
import { DeviceDetailPage } from "../src/pages/DeviceDetailPage";
import { RisksPage } from "../src/pages/RisksPage";
import type { Device, Scan, Risk, RiskSummary } from "../src/types/api";

// ── fixtures ──────────────────────────────────────────────────────────────────

const device1: Device = {
  id: 1,
  ip_address: "10.0.0.1",
  mac_address: "aa:bb:cc:00:00:01",
  vendor: "Cisco",
  hostname: "gw",
  os_guess: "IOS",
  first_seen: "2024-01-01T00:00:00",
  last_seen: "2024-06-01T12:00:00",
  ports: [
    {
      id: 1,
      port_number: 22,
      protocol: "tcp",
      service_name: "ssh",
      version_banner: "OpenSSH",
    },
    {
      id: 2,
      port_number: 80,
      protocol: "tcp",
      service_name: "http",
      version_banner: null,
    },
  ],
};

const device2: Device = {
  id: 2,
  ip_address: "10.0.0.2",
  mac_address: null,
  vendor: null,
  hostname: null,
  os_guess: null,
  first_seen: null,
  last_seen: null,
  ports: [],
};

const scan1: Scan = {
  id: 1,
  status: "completed",
  triggered_by: "manual",
  started_at: "2024-06-01T10:00:00",
  finished_at: "2024-06-01T10:01:00",
  duration_seconds: 60,
  devices_found: 2,
  error_message: null,
};

const risk1: Risk = {
  id: 1,
  device_id: 1,
  severity: "critical",
  check_id: "default_credentials",
  title: "Default credentials",
  description: "Device uses default login credentials.",
  detected_at: "2024-06-01T12:00:00",
};

const summary: RiskSummary = {
  critical: 1,
  high: 0,
  medium: 0,
  low: 0,
  total: 1,
};

// Build a fetch mock that dispatches by URL
function buildFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((url: string) => {
    const defaults: Record<string, unknown> = {
      "/api/devices": [device1, device2],
      "/api/devices/1": device1,
      "/api/scans": [scan1],
      "/api/risks": [risk1],
      "/api/risks/summary": summary,
      "/api/risks?severity=critical": [risk1],
      "/api/risks?device_id=1": [risk1],
      "/api/settings/checklist": {
        items: [],
        posture: "at_risk",
        posture_label: "At Risk",
        yes_count: 0,
      },
      "/api/settings": { webhook_url: null },
      "/api/insights/segmentation": {
        flat_network: false,
        iot_count: 0,
        server_count: 0,
        mixed_risk_pairs: [],
        recommendations: [],
      },
      ...overrides,
    };
    // match base path for parameterised URLs
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

// ── DashboardPage ─────────────────────────────────────────────────────────────

describe("DashboardPage", () => {
  it("renders heading and summary cards", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Total Devices")).toBeInTheDocument(),
    );
    expect(screen.getByText("2")).toBeInTheDocument(); // device count
  });

  it("shows last scan info after loading", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Last Scan")).toBeInTheDocument(),
    );
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows empty scan state when no scans", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/scans": [] }));
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/No scans yet/i)).toBeInTheDocument(),
    );
  });

  it("shows trigger button and calls /api/scans/trigger on click", async () => {
    const fetchMock = buildFetch();
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/scans/trigger") {
        return Promise.resolve({
          ok: true,
          status: 202,
          json: () => Promise.resolve({ message: "started", scan_id: 99 }),
        });
      }
      return buildFetch()(url);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Trigger Scan")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Trigger Scan"));
    await waitFor(() =>
      expect(screen.getByText(/Scan #99 started/i)).toBeInTheDocument(),
    );
  });
});

// ── DevicesPage ───────────────────────────────────────────────────────────────

describe("DevicesPage", () => {
  it("renders device rows", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("10.0.0.1")).toBeInTheDocument(),
    );
    expect(screen.getByText("10.0.0.2")).toBeInTheDocument();
  });

  it("shows empty state when no devices", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/devices": [] }));
    render(
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByText(/No devices discovered yet/i),
      ).toBeInTheDocument(),
    );
  });

  it("filters by search input", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("10.0.0.1")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "10.0.0.1" },
    });
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
    expect(screen.queryByText("10.0.0.2")).not.toBeInTheDocument();
  });

  it("shows no match row when filter yields nothing", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("10.0.0.1")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "zzznomatch" },
    });
    expect(
      screen.getByText(/No devices match the filter/i),
    ).toBeInTheDocument();
  });

  it("shows error message on fetch failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve(null),
      }),
    );
    render(
      <MemoryRouter>
        <DevicesPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/Error:/i)).toBeInTheDocument(),
    );
  });
});

// ── DeviceDetailPage ──────────────────────────────────────────────────────────

describe("DeviceDetailPage", () => {
  function renderDetail(id = "1") {
    return render(
      <MemoryRouter initialEntries={[`/devices/${id}`]}>
        <Routes>
          <Route path="/devices/:id" element={<DeviceDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("renders device IP and port table", async () => {
    vi.stubGlobal("fetch", buildFetch());
    renderDetail("1");
    await waitFor(() =>
      expect(screen.getAllByText("10.0.0.1").length).toBeGreaterThanOrEqual(1),
    );
    expect(screen.getByText("22")).toBeInTheDocument();
    expect(screen.getByText("ssh")).toBeInTheDocument();
  });

  it("shows risk list for device", async () => {
    vi.stubGlobal("fetch", buildFetch());
    renderDetail("1");
    await waitFor(() =>
      expect(screen.getByText("Default credentials")).toBeInTheDocument(),
    );
  });

  it("shows error on failed device fetch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve(null),
      }),
    );
    renderDetail("99");
    await waitFor(() =>
      expect(screen.getByText(/Error:/i)).toBeInTheDocument(),
    );
  });
});

// ── RisksPage ────────────────────────────────────────────────────────────────

describe("RisksPage", () => {
  it("renders risk rows and summary bars", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <RisksPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Default credentials")).toBeInTheDocument(),
    );
    expect(
      screen.getByLabelText(/Filter by critical severity/i),
    ).toBeInTheDocument();
  });

  it("shows empty state when no risks", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/risks": [] }));
    render(
      <MemoryRouter>
        <RisksPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/No risks detected yet/i)).toBeInTheDocument(),
    );
  });

  it("opens risk detail modal on row click", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <RisksPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Default credentials")).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /View details for Default credentials/i,
      }),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("default_credentials")).toBeInTheDocument();
  });

  it("closes modal when clicking close button", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <RisksPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Default credentials")).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /View details for Default credentials/i,
      }),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Close dialog/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("severity filter select is present", async () => {
    vi.stubGlobal("fetch", buildFetch());
    render(
      <MemoryRouter>
        <RisksPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("combobox", { name: /Filter by severity/i }),
    ).toBeInTheDocument();
  });
});
