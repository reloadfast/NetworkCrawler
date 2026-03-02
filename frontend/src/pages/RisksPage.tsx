/**
 * RisksPage — filterable risk list with severity summary cards.
 * Route: /risks
 */
import React, { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, Badge, SkeletonCard, PageHeader } from "../components";
import { SEV_COLORS, SEV_LEVELS } from "../constants/severity";
import { useRisks, useRiskSummary, useDevices } from "../hooks";
import type { Risk, Severity } from "../types/api";

const SEVERITIES: Severity[] = SEV_LEVELS;

type Tab = "active" | "accepted";

// ── Acknowledge modal ─────────────────────────────────────────────────────────

function AcknowledgeModal({
  risk,
  onClose,
  onDone,
}: {
  risk: Risk;
  onClose: () => void;
  onDone: () => void;
}) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = () => {
    setSaving(true);
    fetch(`/api/risks/${risk.id}/acknowledge`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: note.trim() || null }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      })
      .then(onDone)
      .catch(() => setSaving(false));
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Acknowledge risk"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <Card
        className="relative z-10 w-full max-w-md shadow-xl"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Acknowledge risk</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded px-2 py-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            ✕
          </button>
        </div>
        <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
          Mark <strong>{risk.title}</strong> as accepted. It will be hidden from
          the active list and excluded from risk counts. Acknowledgements
          survive re-scans.
        </p>
        <label
          htmlFor="ack-note"
          className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]"
        >
          Reason (optional)
        </label>
        <textarea
          id="ack-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="e.g. FTP is intentional on this NAS"
          rows={3}
          className="mb-4 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)] resize-none"
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="rounded-md bg-[var(--color-accent-primary)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:opacity-90"
          >
            {saving ? "Saving…" : "Acknowledge"}
          </button>
        </div>
      </Card>
    </div>
  );
}

// ── Risk detail modal ─────────────────────────────────────────────────────────

function RiskModal({
  risk,
  onClose,
  onAcknowledge,
  onUnacknowledge,
}: {
  risk: Risk;
  onClose: () => void;
  onAcknowledge: () => void;
  onUnacknowledge: () => void;
}) {
  const [unacking, setUnacking] = useState(false);

  const handleUnacknowledge = () => {
    setUnacking(true);
    fetch(`/api/risks/${risk.id}/unacknowledge`, { method: "PATCH" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      })
      .then(onUnacknowledge)
      .catch(() => setUnacking(false));
  };

  const isAcknowledged = !!risk.acknowledged_at;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Risk detail"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <Card
        className="relative z-10 w-full max-w-lg shadow-xl"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={risk.display_severity ?? risk.severity}>
              {risk.display_severity ?? risk.severity}
            </Badge>
            {isAcknowledged && (
              <span className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs text-[var(--color-text-secondary)]">
                accepted
              </span>
            )}
            <h2 className="text-base font-semibold">{risk.title}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="shrink-0 rounded px-2 py-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            ✕
          </button>
        </div>
        <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
          {risk.description}
        </p>
        {isAcknowledged && risk.acknowledged_note && (
          <div className="mb-4 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Acknowledgement note
            </p>
            <p className="mt-1 text-sm text-[var(--color-text-primary)]">
              {risk.acknowledged_note}
            </p>
          </div>
        )}
        <dl className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Check ID
            </dt>
            <dd className="font-mono">{risk.check_id}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Detected
            </dt>
            <dd>
              {risk.detected_at
                ? new Date(risk.detected_at).toLocaleString()
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Device
            </dt>
            <dd>
              <Link
                to={`/devices/${risk.device_id}`}
                className="text-[var(--color-accent-positive)] hover:underline"
                onClick={onClose}
              >
                {risk.label ?? risk.hostname ?? risk.ip_address}
              </Link>
            </dd>
          </div>
          {isAcknowledged && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Acknowledged
              </dt>
              <dd>{new Date(risk.acknowledged_at!).toLocaleString()}</dd>
            </div>
          )}
        </dl>
        <div className="flex justify-end">
          {isAcknowledged ? (
            <button
              onClick={handleUnacknowledge}
              disabled={unacking}
              className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
            >
              {unacking ? "Restoring…" : "Reopen risk"}
            </button>
          ) : (
            <button
              onClick={onAcknowledge}
              className="rounded-md border border-[var(--color-accent-primary)]/40 px-3 py-1.5 text-sm text-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary)]/10"
            >
              Acknowledge
            </button>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function RisksPage() {
  const [searchParams] = useSearchParams();
  const initialSev = searchParams.get("severity");
  const [tab, setTab] = useState<Tab>("active");
  const [sevFilter, setSevFilter] = useState<Severity | "">(
    SEVERITIES.includes(initialSev as Severity) ? (initialSev as Severity) : "",
  );
  const [devFilter, setDevFilter] = useState<number | "">("");
  const [selectedRisk, setSelectedRisk] = useState<Risk | null>(null);
  const [ackTarget, setAckTarget] = useState<Risk | null>(null);

  const acknowledged = tab === "accepted" ? true : false;

  const { risks, loading, error, refetch } = useRisks({
    severity: sevFilter || undefined,
    deviceId: devFilter !== "" ? devFilter : undefined,
    acknowledged,
  });
  const { summary, refetch: refetchSummary } = useRiskSummary();
  const { devices } = useDevices();

  const totalRisks = summary?.total ?? 0;

  const summaryCards = useMemo(
    () =>
      SEV_LEVELS.map((sev) => ({
        sev,
        count: summary?.[sev] ?? 0,
        pct:
          totalRisks > 0
            ? Math.round(((summary?.[sev] ?? 0) / totalRisks) * 100)
            : 0,
        color: SEV_COLORS[sev],
      })),
    [summary, totalRisks],
  );

  const handleAckDone = () => {
    setAckTarget(null);
    setSelectedRisk(null);
    refetch();
    refetchSummary();
  };

  const handleUnackDone = () => {
    setSelectedRisk(null);
    refetch();
    refetchSummary();
  };

  return (
    <div>
      <PageHeader
        title="Risks"
        subtitle={
          totalRisks > 0
            ? `${totalRisks} active risk${totalRisks !== 1 ? "s" : ""}`
            : undefined
        }
      />

      {/* Severity summary cards — active risks only */}
      {summary && tab === "active" && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {summaryCards.map(({ sev, count, pct, color }) => (
            <button
              key={sev}
              onClick={() => setSevFilter(sev === sevFilter ? "" : sev)}
              className={[
                "group relative overflow-hidden rounded-xl border p-4 text-left transition-all duration-150",
                sevFilter === sev
                  ? "border-[var(--color-accent-primary)]/60 bg-[var(--color-surface)]"
                  : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border)]",
              ].join(" ")}
              style={{ borderLeft: `3px solid ${color}` }}
              aria-pressed={sevFilter === sev}
              aria-label={`Filter by ${sev} severity (${count})`}
            >
              <p
                className="text-xs font-semibold uppercase tracking-widest"
                style={{ color }}
              >
                {sev}
              </p>
              <p className="mt-1 text-2xl font-bold text-[var(--color-text-primary)]">
                {count}
              </p>
              <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
                {pct}% of total
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Active / Accepted tabs */}
      <div className="mb-4 flex gap-1 border-b border-[var(--color-border)]">
        {(["active", "accepted"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
              tab === t
                ? "border-[var(--color-accent-primary)] text-[var(--color-accent-primary)]"
                : "border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
            ].join(" ")}
          >
            {t === "active" ? "Active" : "Accepted"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={sevFilter}
          onChange={(e) => setSevFilter(e.target.value as Severity | "")}
          aria-label="Filter by severity"
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
        >
          <option value="">All severities</option>
          {SEV_LEVELS.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <select
          value={devFilter}
          onChange={(e) =>
            setDevFilter(e.target.value ? Number(e.target.value) : "")
          }
          aria-label="Filter by device"
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
        >
          <option value="">All devices</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label ?? d.ip_address}
              {!d.label && d.hostname ? ` (${d.hostname})` : ""}
            </option>
          ))}
        </select>

        {(sevFilter || devFilter) && (
          <button
            onClick={() => {
              setSevFilter("");
              setDevFilter("");
            }}
            className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            Clear filters ✕
          </button>
        )}
      </div>

      {/* Risk list */}
      {loading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} height="16" />
          ))}
        </div>
      )}
      {error && (
        <p className="text-[var(--color-accent-danger)]">Error: {error}</p>
      )}

      {!loading && !error && risks.length === 0 && (
        <Card>
          <p className="py-8 text-center text-[var(--color-text-secondary)]">
            {tab === "accepted"
              ? "No accepted risks. Acknowledge risks from the Active tab to suppress them."
              : sevFilter || devFilter
                ? "No risks match the selected filters."
                : "No risks detected yet. Run a scan from the Dashboard."}
          </p>
        </Card>
      )}

      {!loading && !error && risks.length > 0 && (
        <Card padding="none">
          <div className="divide-y divide-[var(--color-border)]">
            {risks.map((risk) => {
              const deviceLabel =
                risk.label ?? risk.hostname ?? risk.ip_address;
              return (
                <button
                  key={risk.id}
                  className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--color-background)]"
                  onClick={() => setSelectedRisk(risk)}
                  aria-label={`View details for ${risk.title}`}
                >
                  <Badge variant={risk.display_severity ?? risk.severity}>
                    {risk.display_severity ?? risk.severity}
                  </Badge>
                  <span className="flex-1 text-sm font-medium">
                    {risk.title}
                  </span>
                  <Link
                    to={`/devices/${risk.device_id}`}
                    className="text-xs text-[var(--color-accent-positive)] hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {deviceLabel}
                  </Link>
                  <span className="text-xs text-[var(--color-text-secondary)]">
                    {risk.detected_at
                      ? new Date(risk.detected_at).toLocaleDateString()
                      : "—"}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {selectedRisk && (
        <RiskModal
          risk={selectedRisk}
          onClose={() => setSelectedRisk(null)}
          onAcknowledge={() => {
            setAckTarget(selectedRisk);
          }}
          onUnacknowledge={handleUnackDone}
        />
      )}

      {ackTarget && (
        <AcknowledgeModal
          risk={ackTarget}
          onClose={() => setAckTarget(null)}
          onDone={handleAckDone}
        />
      )}
    </div>
  );
}
