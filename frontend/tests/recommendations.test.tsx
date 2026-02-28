/**
 * Tests for useRecommendations / useDeviceRecommendations hooks
 * and RecommendationsPage / RecommendationDetailPage components.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
  useRecommendations,
  useDeviceRecommendations,
} from "../src/hooks/useRecommendations";
import { RecommendationsPage } from "../src/pages/RecommendationsPage";
import { RecommendationDetailPage } from "../src/pages/RecommendationDetailPage";
import type { Recommendation } from "../src/types/api";

// ── fixtures ──────────────────────────────────────────────────────────────────

const rec1: Recommendation = {
  id: 1,
  device_id: 10,
  risk_id: 5,
  check_id: "telnet_open",
  severity: "critical",
  title: "Disable Telnet",
  description: "Telnet transmits data in plaintext.",
  steps: [
    "Step one: disable telnet service",
    "Step two: verify port 23 closed",
  ],
  effort: "low",
  impact: "high",
  created_at: "2024-06-01T00:00:00",
  updated_at: null,
};

const rec2: Recommendation = {
  id: 2,
  device_id: 11,
  risk_id: 6,
  check_id: "ftp_open",
  severity: "high",
  title: "Disable FTP",
  description: "FTP transmits credentials in plaintext.",
  steps: ["Disable FTP server", "Use SFTP instead"],
  effort: "medium",
  impact: "medium",
  created_at: "2024-06-01T00:00:00",
  updated_at: null,
};

function mockFetch(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  });
}

beforeEach(() => vi.restoreAllMocks());

// ── useRecommendations ────────────────────────────────────────────────────────

describe("useRecommendations", () => {
  it("returns recommendations on success", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1, rec2]));
    const { result } = renderHook(() => useRecommendations());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.recommendations).toHaveLength(2);
    expect(result.current.recommendations[0].title).toBe("Disable Telnet");
    expect(result.current.error).toBeNull();
  });

  it("sets error on HTTP failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    const { result } = renderHook(() => useRecommendations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toMatch(/HTTP 500/);
    expect(result.current.recommendations).toHaveLength(0);
  });

  it("appends device_id filter to query string", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRecommendations({ deviceId: 42 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("device_id=42");
  });

  it("appends severity filter to query string", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useRecommendations({ severity: "critical" }),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("severity=critical");
  });

  it("fetches without query string when no filters", async () => {
    const fetchMock = mockFetch([]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRecommendations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/api/recommendations");
  });

  it("refetch re-fetches data", async () => {
    const fetchMock = mockFetch([rec1]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useRecommendations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    result.current.refetch();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});

// ── useDeviceRecommendations ──────────────────────────────────────────────────

describe("useDeviceRecommendations", () => {
  it("fetches from device-scoped endpoint", async () => {
    const fetchMock = mockFetch([rec1]);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useDeviceRecommendations(10));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.recommendations).toHaveLength(1);
    expect(result.current.recommendations[0].check_id).toBe("telnet_open");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/api/devices/10/recommendations");
  });

  it("sets error on failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    const { result } = renderHook(() => useDeviceRecommendations(99));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeTruthy();
    expect(result.current.recommendations).toHaveLength(0);
  });
});

// ── RecommendationsPage ───────────────────────────────────────────────────────

describe("RecommendationsPage", () => {
  it("renders list of recommendations", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1, rec2]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Disable Telnet")).toBeInTheDocument(),
    );
    expect(screen.getByText("Disable FTP")).toBeInTheDocument();
  });

  it("shows empty state when no recommendations", async () => {
    vi.stubGlobal("fetch", mockFetch([]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/No recommendations yet/i)).toBeInTheDocument(),
    );
  });

  it("shows error on fetch failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/Error:/i)).toBeInTheDocument(),
    );
  });

  it("renders sort select with default severity option", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Disable Telnet")).toBeInTheDocument(),
    );
    const select = screen.getByRole("combobox", {
      name: /Sort recommendations/i,
    });
    expect(select).toBeInTheDocument();
    expect((select as HTMLSelectElement).value).toBe("severity");
  });

  it("changes sort key when select changes", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1, rec2]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Disable Telnet")).toBeInTheDocument(),
    );
    const select = screen.getByRole("combobox", {
      name: /Sort recommendations/i,
    });
    fireEvent.change(select, { target: { value: "effort" } });
    expect((select as HTMLSelectElement).value).toBe("effort");
  });

  it("displays effort and impact chips", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Disable Telnet")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("Effort: low")).toBeInTheDocument();
    expect(screen.getByLabelText("Impact: high")).toBeInTheDocument();
  });

  it("shows device link for each recommendation", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    render(
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Device #10")).toBeInTheDocument(),
    );
  });
});

// ── RecommendationDetailPage ──────────────────────────────────────────────────

describe("RecommendationDetailPage", () => {
  function renderDetail(id = "1") {
    return render(
      <MemoryRouter initialEntries={[`/recommendations/${id}`]}>
        <Routes>
          <Route
            path="/recommendations/:id"
            element={<RecommendationDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("renders title, description, and steps", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    renderDetail("1");
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Disable Telnet" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Telnet transmits data in plaintext."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Step one: disable telnet service"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Step two: verify port 23 closed"),
    ).toBeInTheDocument();
  });

  it("shows breadcrumb link back to recommendations", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    renderDetail("1");
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Disable Telnet" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("← Recommendations")).toBeInTheDocument();
  });

  it("shows device link", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    renderDetail("1");
    await waitFor(() =>
      expect(screen.getByText(/Device #10/i)).toBeInTheDocument(),
    );
  });

  it("shows effort and impact bars", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    renderDetail("1");
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Disable Telnet" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("Effort: low")).toBeInTheDocument();
    expect(screen.getByLabelText("Impact: high")).toBeInTheDocument();
  });

  it("shows not found message for unknown id", async () => {
    vi.stubGlobal("fetch", mockFetch([rec1]));
    renderDetail("999");
    await waitFor(() =>
      expect(screen.getByText(/Recommendation not found/i)).toBeInTheDocument(),
    );
  });

  it("shows error on fetch failure", async () => {
    vi.stubGlobal("fetch", mockFetch(null, false));
    renderDetail("1");
    await waitFor(() =>
      expect(screen.getByText(/Error:/i)).toBeInTheDocument(),
    );
  });
});
