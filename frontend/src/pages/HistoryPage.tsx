/**
 * HistoryPage — scan history with device-count and risk-severity trend charts.
 * Route: /history
 */
import { useMemo } from "react";
import { Card, PageHeader, SkeletonCard } from "../components";
import { useScans } from "../hooks";
import type { Scan } from "../types/api";

// ── Colour palette ────────────────────────────────────────────────────────────
const SEV_COLORS = {
  critical: "var(--color-accent-danger)",
  high: "var(--color-accent-warning)",
  medium: "var(--color-accent-caution)",
  low: "var(--color-accent-positive)",
} as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── Bar chart (device count trend) ────────────────────────────────────────────

interface BarChartProps {
  data: { label: string; value: number }[];
  color?: string;
  height?: number;
}

function BarChart({
  data,
  color = "var(--color-accent-primary)",
  height = 120,
}: BarChartProps) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const barW = Math.max(8, Math.floor(320 / Math.max(data.length, 1)) - 4);
  const svgW = data.length * (barW + 4) + 4;

  return (
    <div className="overflow-x-auto">
      <svg
        width={svgW}
        height={height + 20}
        aria-label="Device count per scan"
        role="img"
        style={{ minWidth: svgW }}
      >
        {data.map((d, i) => {
          const barH = Math.max(2, Math.round((d.value / max) * height));
          const x = i * (barW + 4) + 2;
          const y = height - barH;
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={barH}
                fill={color}
                rx={2}
                opacity={0.85}
              >
                <title>{`${d.label}: ${d.value} devices`}</title>
              </rect>
              <text
                x={x + barW / 2}
                y={height + 14}
                textAnchor="middle"
                fontSize={9}
                fill="var(--color-text-secondary)"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Stacked bar chart (risk severity trend) ───────────────────────────────────

type SevKey = "critical" | "high" | "medium" | "low";
const SEV_KEYS: SevKey[] = ["critical", "high", "medium", "low"];

interface StackedBarChartProps {
  data: {
    label: string;
    critical: number;
    high: number;
    medium: number;
    low: number;
  }[];
  height?: number;
}

function StackedBarChart({ data, height = 120 }: StackedBarChartProps) {
  const totals = data.map((d) => d.critical + d.high + d.medium + d.low);
  const max = Math.max(...totals, 1);
  const barW = Math.max(8, Math.floor(320 / Math.max(data.length, 1)) - 4);
  const svgW = data.length * (barW + 4) + 4;

  return (
    <div className="overflow-x-auto">
      <svg
        width={svgW}
        height={height + 20}
        aria-label="Risk counts per scan"
        role="img"
        style={{ minWidth: svgW }}
      >
        {data.map((d, i) => {
          const x = i * (barW + 4) + 2;
          let yOffset = height;
          return (
            <g key={i}>
              {SEV_KEYS.map((sev) => {
                const val = d[sev];
                const segH = Math.round((val / max) * height);
                yOffset -= segH;
                return segH > 0 ? (
                  <rect
                    key={sev}
                    x={x}
                    y={yOffset}
                    width={barW}
                    height={segH}
                    fill={SEV_COLORS[sev]}
                    opacity={0.85}
                    rx={sev === "low" ? 2 : 0}
                  >
                    <title>{`${d.label} — ${sev}: ${val}`}</title>
                  </rect>
                ) : null;
              })}
              <text
                x={x + barW / 2}
                y={height + 14}
                textAnchor="middle"
                fontSize={9}
                fill="var(--color-text-secondary)"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function SevLegend() {
  return (
    <div className="mt-2 flex flex-wrap gap-3">
      {SEV_KEYS.map((sev) => (
        <span
          key={sev}
          className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)]"
        >
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: SEV_COLORS[sev] }}
          />
          {sev.charAt(0).toUpperCase() + sev.slice(1)}
        </span>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function HistoryPage() {
  const { scans, loading, error } = useScans();

  // Oldest → newest for charts (API returns newest first)
  const completed = useMemo(
    () =>
      [...scans]
        .filter((s: Scan) => s.status === "completed")
        .sort((a, b) => (a.started_at ?? "").localeCompare(b.started_at ?? "")),
    [scans],
  );

  const deviceData = useMemo(
    () =>
      completed.map((s) => ({
        label: shortDate(s.started_at),
        value: s.devices_found ?? 0,
      })),
    [completed],
  );

  const riskData = useMemo(
    () =>
      completed.map((s) => ({
        label: shortDate(s.started_at),
        critical: s.risks_critical ?? 0,
        high: s.risks_high ?? 0,
        medium: s.risks_medium ?? 0,
        low: s.risks_low ?? 0,
      })),
    [completed],
  );

  return (
    <div>
      <PageHeader
        title="Scan History"
        subtitle={
          scans.length > 0
            ? `${scans.length} scan${scans.length !== 1 ? "s" : ""} recorded`
            : undefined
        }
      />

      {loading && (
        <div className="flex flex-col gap-4">
          <SkeletonCard height="32" />
          <SkeletonCard height="32" />
        </div>
      )}
      {error && (
        <p className="text-[var(--color-accent-danger)]">Error: {error}</p>
      )}

      {!loading && !error && completed.length === 0 && (
        <Card>
          <p className="py-8 text-center text-[var(--color-text-secondary)]">
            No completed scans yet. Run a scan from the Dashboard.
          </p>
        </Card>
      )}

      {!loading && !error && completed.length > 0 && (
        <div className="flex flex-col gap-6">
          {/* Device count trend */}
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
              Devices discovered per scan
            </h2>
            <BarChart data={deviceData} />
          </Card>

          {/* Risk trend */}
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
              Risk counts per scan
            </h2>
            <StackedBarChart data={riskData} />
            <SevLegend />
          </Card>

          {/* Scan table */}
          <Card padding="none">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">By</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3 text-right">Devices</th>
                    <th className="px-4 py-3 text-right">Critical</th>
                    <th className="px-4 py-3 text-right">High</th>
                    <th className="px-4 py-3 text-right">Medium</th>
                    <th className="px-4 py-3 text-right">Low</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {[...scans].map((s) => (
                    <tr
                      key={s.id}
                      className="hover:bg-[var(--color-background)]"
                    >
                      <td className="px-4 py-2 text-[var(--color-text-secondary)]">
                        {shortDate(s.started_at)}
                      </td>
                      <td className="px-4 py-2 capitalize">
                        {s.triggered_by}
                        {s.warning_message && (
                          <span
                            title={s.warning_message}
                            className="ml-1 cursor-help text-[var(--color-accent-warning)]"
                          >
                            ⚠
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-[var(--color-text-secondary)]">
                        {s.duration_seconds != null
                          ? `${s.duration_seconds}s`
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {s.devices_found ?? "—"}
                      </td>
                      <td
                        className="px-4 py-2 text-right"
                        style={{ color: SEV_COLORS.critical }}
                      >
                        {s.risks_critical ?? "—"}
                      </td>
                      <td
                        className="px-4 py-2 text-right"
                        style={{ color: SEV_COLORS.high }}
                      >
                        {s.risks_high ?? "—"}
                      </td>
                      <td
                        className="px-4 py-2 text-right"
                        style={{ color: SEV_COLORS.medium }}
                      >
                        {s.risks_medium ?? "—"}
                      </td>
                      <td
                        className="px-4 py-2 text-right"
                        style={{ color: SEV_COLORS.low }}
                      >
                        {s.risks_low ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
