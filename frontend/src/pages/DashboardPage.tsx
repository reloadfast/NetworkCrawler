/**
 * DashboardPage — summary cards, last scan info, and quick-trigger button.
 * Route: /
 */
import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Badge } from '../components'
import { useDevices, useScans, useTriggerScan, useRiskSummary } from '../hooks'

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <Card>
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
        {label}
      </p>
      <p className="text-3xl font-bold text-[var(--color-text-primary)]">{value}</p>
      {sub && <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{sub}</p>}
    </Card>
  )
}

export function DashboardPage() {
  const { devices, loading: devLoading } = useDevices()
  const { scans, loading: scanLoading, refetch: refetchScans } = useScans()
  const { summary, loading: summaryLoading } = useRiskSummary()
  const { trigger, loading: triggering } = useTriggerScan()
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null)

  const lastScan = scans[0] ?? null

  const handleTrigger = async () => {
    setTriggerMsg(null)
    const result = await trigger()
    if (result) {
      setTriggerMsg(`Scan #${result.scan_id ?? '?'} started`)
      refetchScans()
    }
  }

  const loading = devLoading || scanLoading || summaryLoading

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <div className="flex items-center gap-3">
          {triggerMsg && (
            <span className="text-sm text-[var(--color-accent-positive)]">{triggerMsg}</span>
          )}
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm font-medium text-[var(--color-text-primary)] transition-colors duration-150 hover:border-[var(--color-accent-positive)] disabled:opacity-50"
          >
            {triggering ? 'Scanning…' : 'Trigger Scan'}
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-[var(--color-text-secondary)]">Loading…</p>
      ) : (
        <>
          {/* Summary cards */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total Devices" value={devices.length} />
            <StatCard
              label="Critical"
              value={<span className="text-[var(--color-accent-danger)]">{summary?.critical ?? 0}</span>}
              sub="risks"
            />
            <StatCard
              label="High"
              value={<span className="text-[var(--color-accent-danger)]">{summary?.high ?? 0}</span>}
              sub="risks"
            />
            <StatCard
              label="Medium / Low"
              value={(summary?.medium ?? 0) + (summary?.low ?? 0)}
              sub="risks"
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
                    lastScan.status === 'completed'
                      ? 'low'
                      : lastScan.status === 'failed'
                        ? 'critical'
                        : 'medium'
                  }
                >
                  {lastScan.status}
                </Badge>
                <span className="text-[var(--color-text-secondary)]">
                  {lastScan.started_at
                    ? new Date(lastScan.started_at).toLocaleString()
                    : 'Unknown time'}
                </span>
                {lastScan.duration_seconds != null && (
                  <span className="text-[var(--color-text-secondary)]">
                    {lastScan.duration_seconds.toFixed(1)}s
                  </span>
                )}
                {lastScan.devices_found != null && (
                  <span className="text-[var(--color-text-secondary)]">
                    {lastScan.devices_found} device{lastScan.devices_found !== 1 ? 's' : ''} found
                  </span>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-secondary)]">No scans yet.</p>
            )}
          </Card>

          {/* Quick links */}
          <div className="flex gap-3 text-sm">
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
    </div>
  )
}
