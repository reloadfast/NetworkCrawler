/**
 * DashboardPage — summary cards, last scan info, and quick-trigger button.
 * Route: /
 */
import React, { memo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  Badge,
  ScanBanner,
  ToastContainer,
  SkeletonCard,
  PageHeader,
} from "../components";
import { useDevices, useScans, useTriggerScan, useRiskSummary } from "../hooks";
import { useScanStatus } from "../hooks/useScanStatus";
import { useToast } from "../hooks/useToast";

// ── Accent stripe colours per stat card ───────────────────────────────────────
const STRIPE: Record<string, string> = {
  devices: "var(--color-accent-primary)",
  critical: "var(--color-accent-danger)",
  high: "var(--color-accent-warning)",
  other: "var(--color-accent-positive)",
};

function DeviceIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function CriticalIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

const StatCard = memo(function StatCard({
  label,
  value,
  sub,
  accentColor,
  icon,
  to,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  accentColor: string;
  icon: React.ReactNode;
  to?: string;
}) {
  const inner = (
    <div
      className="relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 transition-all duration-150 hover:border-[var(--color-accent-primary)]/50 hover:shadow-md"
      style={{
        borderLeft: `3px solid ${accentColor}`,
        cursor: to ? "pointer" : "default",
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
            {label}
          </p>
          <p className="text-3xl font-bold text-[var(--color-text-primary)]">
            {value}
          </p>
          {sub && (
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              {sub}
            </p>
          )}
        </div>
        <div style={{ color: accentColor }} className="opacity-60 mt-0.5">
          {icon}
        </div>
      </div>
    </div>
  );
  return to ? <Link to={to}>{inner}</Link> : inner;
});

export function DashboardPage() {
  const { devices, loading: devLoading } = useDevices();
  const { scans, loading: scanLoading, refetch: refetchScans } = useScans();
  const { summary, loading: summaryLoading } = useRiskSummary();
  const { trigger, loading: triggering } = useTriggerScan();
  const { isRunning, latestScan: runningScan } = useScanStatus();
  const { toasts, addToast, dismissToast } = useToast();
  const [scanStartedId, setScanStartedId] = useState<number | null>(null);

  const lastScan = scans[0] ?? null;
  const loading = devLoading || scanLoading || summaryLoading;
  const noScansYet = !loading && scans.length === 0;

  const handleTrigger = async () => {
    const result = await trigger();
    if (result) {
      setScanStartedId(result.scan_id ?? null);
      addToast(`Scan #${result.scan_id ?? "?"} started`, "info");
      refetchScans();
    } else {
      addToast("Failed to trigger scan", "error");
    }
  };

  const activeScanId =
    scanStartedId ?? (isRunning ? (runningScan?.id ?? null) : null);

  const triggerButton = (
    <button
      onClick={handleTrigger}
      disabled={triggering || isRunning}
      aria-label={
        triggering || isRunning ? "Scan in progress" : "Trigger a new scan"
      }
      className="flex items-center gap-2 rounded-lg bg-[var(--color-accent-primary)]/10 border border-[var(--color-accent-primary)]/30 px-4 py-2 text-sm font-medium text-[var(--color-accent-primary)] transition-colors duration-150 hover:bg-[var(--color-accent-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {(triggering || isRunning) && (
        <span
          className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {triggering ? "Starting…" : isRunning ? "Scanning…" : "Trigger Scan"}
    </button>
  );

  return (
    <div className="page-enter">
      {isRunning && <ScanBanner scanId={activeScanId} />}

      <PageHeader title="Dashboard" action={triggerButton} />

      {noScansYet && (
        <Card className="mb-6 flex flex-col items-center gap-4 py-10 text-center">
          <div className="text-4xl">🛡️</div>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            Welcome to NetworkCrawler
          </h2>
          <p className="max-w-md text-sm text-[var(--color-text-secondary)]">
            Discover every device on your LAN, identify misconfigurations, and
            get actionable hardening advice — all locally, with no data leaving
            your network.
          </p>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="mt-2 rounded-lg bg-[var(--color-accent-primary)] px-6 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {triggering ? "Starting…" : "Run your first scan"}
          </button>
        </Card>
      )}

      {loading ? (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} height="24" />
          ))}
        </div>
      ) : (
        <>
          {/* Summary stat cards */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total Devices"
              value={devices.length}
              accentColor={STRIPE.devices}
              icon={<DeviceIcon />}
              to="/devices"
            />
            <StatCard
              label="Critical Risks"
              value={
                <span style={{ color: STRIPE.critical }}>
                  {summary?.critical ?? 0}
                </span>
              }
              accentColor={STRIPE.critical}
              icon={<CriticalIcon />}
              to="/risks?severity=critical"
            />
            <StatCard
              label="High Risks"
              value={
                <span style={{ color: STRIPE.high }}>{summary?.high ?? 0}</span>
              }
              accentColor={STRIPE.high}
              icon={<WarningIcon />}
              to="/risks?severity=high"
            />
            <StatCard
              label="Medium / Low"
              value={(summary?.medium ?? 0) + (summary?.low ?? 0)}
              sub="risks"
              accentColor={STRIPE.other}
              icon={<ShieldIcon />}
              to="/risks"
            />
          </div>

          {/* Last scan */}
          <Card className="mb-6">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
              Last Scan
            </p>
            {lastScan ? (
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <Badge
                  variant={
                    lastScan.status === "completed"
                      ? "low"
                      : lastScan.status === "failed"
                        ? "critical"
                        : "medium"
                  }
                >
                  {lastScan.status}
                </Badge>
                <span className="text-[var(--color-text-secondary)]">
                  {lastScan.started_at
                    ? new Date(lastScan.started_at).toLocaleString()
                    : "Unknown time"}
                </span>
                {lastScan.duration_seconds != null && (
                  <span className="text-[var(--color-text-secondary)]">
                    {lastScan.duration_seconds.toFixed(1)}s
                  </span>
                )}
                {lastScan.devices_found != null && (
                  <span className="text-[var(--color-text-secondary)]">
                    {lastScan.devices_found} device
                    {lastScan.devices_found !== 1 ? "s" : ""} found
                  </span>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-secondary)]">
                No scans yet. Trigger a scan to get started.
              </p>
            )}
          </Card>

          {/* Quick links */}
          <div className="flex gap-4 text-sm">
            <Link
              to="/devices"
              className="text-[var(--color-accent-positive)] underline-offset-2 hover:underline"
            >
              View all devices →
            </Link>
            <Link
              to="/risks"
              className="text-[var(--color-accent-warning)] underline-offset-2 hover:underline"
            >
              View all risks →
            </Link>
          </div>
        </>
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
