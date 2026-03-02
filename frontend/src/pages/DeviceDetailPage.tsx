/**
 * DeviceDetailPage — ports/services table, risk list, timestamps.
 * Route: /devices/:id
 */
import { memo, useRef, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Card,
  Badge,
  SkeletonCard,
  PageHeader,
  ScoreBadge,
  DeviceTypeBadge,
} from "../components";
import { SEV_LEVELS } from "../constants/severity";
import { useDevice, useRisks, useDeviceRecommendations } from "../hooks";
import type { Risk, Recommendation, Severity } from "../types/api";

const SEV_ORDER: Severity[] = SEV_LEVELS;

const RiskCard = memo(function RiskCard({ risk }: { risk: Risk }) {
  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <Badge variant={risk.display_severity ?? risk.severity}>
          {risk.display_severity ?? risk.severity}
        </Badge>
        <span className="font-medium">{risk.title}</span>
      </div>
      <p className="text-sm text-[var(--color-text-secondary)]">
        {risk.description}
      </p>
      <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
        Check: <span className="font-mono">{risk.check_id}</span>
        {risk.detected_at && (
          <> &middot; Detected {new Date(risk.detected_at).toLocaleString()}</>
        )}
      </p>
    </Card>
  );
});

const RecCard = memo(function RecCard({ rec }: { rec: Recommendation }) {
  return (
    <Card>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Badge variant={rec.severity}>{rec.severity}</Badge>
        <Link
          to={`/recommendations/${rec.id}`}
          className="font-medium hover:underline text-[var(--color-text-primary)]"
        >
          {rec.title}
        </Link>
      </div>
      <p className="text-sm text-[var(--color-text-secondary)]">
        {rec.description}
      </p>
    </Card>
  );
});

/** A risk paired with its linked recommendation (if any). */
const RiskRecPair = memo(function RiskRecPair({
  risk,
  rec,
}: {
  risk: Risk;
  rec: Recommendation | undefined;
}) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <RiskCard risk={risk} />
      {rec ? (
        <RecCard rec={rec} />
      ) : (
        <Card>
          <p className="py-2 text-sm italic text-[var(--color-text-secondary)]">
            No remediation available for this risk.
          </p>
        </Card>
      )}
    </div>
  );
});

export function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const deviceId = Number(id);
  const { device, loading, error, refetch } = useDevice(deviceId);
  const { risks, loading: risksLoading } = useRisks({ deviceId });
  const { recommendations, loading: recsLoading } =
    useDeviceRecommendations(deviceId);
  const [togglingTrust, setTogglingTrust] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [label, setLabel] = useState<string | null | undefined>(undefined); // undefined = use device.label
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const [savingLabel, setSavingLabel] = useState(false);
  const labelInputRef = useRef<HTMLInputElement>(null);

  const displayLabel = label !== undefined ? label : device?.label;

  // Build a map of risk_id → recommendation for O(1) lookup
  const recByRiskId = useMemo(() => {
    const map = new Map<number, Recommendation>();
    recommendations.forEach((r) => map.set(r.risk_id, r));
    return map;
  }, [recommendations]);

  // Recommendations not linked to any risk shown in the list
  const linkedRiskIds = useMemo(() => new Set(risks.map((r) => r.id)), [risks]);
  const orphanRecs = useMemo(
    () => recommendations.filter((r) => !linkedRiskIds.has(r.risk_id)),
    [recommendations, linkedRiskIds],
  );

  if (loading) return <SkeletonCard height="48" />;
  if (error)
    return <p className="text-[var(--color-accent-danger)]">Error: {error}</p>;
  if (!device)
    return (
      <p className="text-[var(--color-text-secondary)]">Device not found.</p>
    );

  const sortedRisks = [...risks].sort(
    (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity),
  );

  const handleSaveLabel = () => {
    setSavingLabel(true);
    const newLabel = labelDraft.trim() || null;
    fetch(`/api/devices/${deviceId}/label`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel }),
    })
      .then((r) => r.json())
      .then((d: { label: string | null }) => setLabel(d.label))
      .catch(() => {})
      .finally(() => {
        setSavingLabel(false);
        setEditingLabel(false);
      });
  };

  const handleToggleTrust = () => {
    setTogglingTrust(true);
    fetch(`/api/devices/${deviceId}/trusted`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trusted: !device.trusted }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      })
      .then(() => refetch())
      .catch(() => {
        setToastMsg("Failed to update trusted status. Please try again.");
      })
      .finally(() => setTogglingTrust(false));
  };

  return (
    <div>
      {toastMsg && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-[var(--color-accent-danger)]/40 bg-[var(--color-accent-danger)]/10 px-4 py-2.5 text-sm text-[var(--color-accent-danger)]"
        >
          {toastMsg}
          <button
            onClick={() => setToastMsg(null)}
            className="ml-3 font-bold opacity-70 hover:opacity-100"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}
      <div className="mb-1 flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
        <Link
          to="/devices"
          className="hover:text-[var(--color-text-primary)] transition-colors"
        >
          Devices
        </Link>
        <span className="opacity-40">/</span>
        <span className="font-mono text-[var(--color-text-primary)]">
          {device.ip_address}
        </span>
      </div>
      <PageHeader
        title={displayLabel ?? device.hostname ?? device.ip_address}
        subtitle={
          displayLabel != null
            ? (device.hostname ?? device.ip_address)
            : device.hostname != null
              ? device.ip_address
              : undefined
        }
        action={
          <div className="flex items-center gap-3">
            {device.trusted && (
              <Badge variant="neutral" className="gap-1">
                🛡 Trusted
              </Badge>
            )}
            <button
              onClick={handleToggleTrust}
              disabled={togglingTrust}
              className={[
                "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                "focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]",
                device.trusted
                  ? "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent-danger)] hover:text-[var(--color-accent-danger)]"
                  : "border-[var(--color-accent-primary)]/40 text-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary)]/10",
              ].join(" ")}
            >
              {togglingTrust
                ? "…"
                : device.trusted
                  ? "Untrust device"
                  : "Mark as trusted"}
            </button>
          </div>
        }
      />

      {/* Device metadata */}
      <Card className="mb-6">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {/* Label — inline editable */}
          <div className="flex flex-col">
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Label
            </dt>
            <dd className="font-mono text-[var(--color-text-primary)]">
              {editingLabel ? (
                <input
                  ref={labelInputRef}
                  autoFocus
                  value={labelDraft}
                  onChange={(e) => setLabelDraft(e.target.value)}
                  onBlur={handleSaveLabel}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      labelInputRef.current?.blur();
                    } else if (e.key === "Escape") {
                      setEditingLabel(false);
                    }
                  }}
                  disabled={savingLabel}
                  className="w-full rounded border border-[var(--color-accent-primary)] bg-[var(--color-background)] px-1.5 py-0.5 text-sm focus:outline-none"
                  placeholder="Add label…"
                />
              ) : (
                <span className="group flex items-center gap-1.5">
                  <span
                    className={
                      !displayLabel
                        ? "text-[var(--color-text-secondary)]"
                        : undefined
                    }
                  >
                    {displayLabel ?? "—"}
                  </span>
                  <button
                    onClick={() => {
                      setLabelDraft(displayLabel ?? "");
                      setEditingLabel(true);
                    }}
                    aria-label="Edit label"
                    title="Edit label"
                    className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-xs transition-opacity"
                  >
                    ✏
                  </button>
                </span>
              )}
            </dd>
          </div>
          {[
            ["Hostname", device.hostname ?? "—"],
            ["MAC Address", device.mac_address ?? "—"],
            ["Vendor", device.vendor ?? "—"],
            ["OS", device.os_guess ?? "—"],
            [
              "First Seen",
              device.first_seen
                ? new Date(device.first_seen).toLocaleString()
                : "—",
            ],
            [
              "Last Seen",
              device.last_seen
                ? new Date(device.last_seen).toLocaleString()
                : "—",
            ],
          ].map(([lbl, value]) => (
            <div key={lbl} className="flex flex-col">
              <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                {lbl}
              </dt>
              <dd className="font-mono text-[var(--color-text-primary)]">
                {value}
              </dd>
            </div>
          ))}
          <div className="flex flex-col">
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Device Type
            </dt>
            <dd className="mt-1">
              <DeviceTypeBadge type={device.device_type} size="md" />
            </dd>
          </div>
          <div className="flex flex-col">
            <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Security Score
            </dt>
            <dd className="mt-1">
              <ScoreBadge score={device.security_score} size="lg" />
              <span className="ml-2 text-xs text-[var(--color-text-secondary)]">
                / 100
              </span>
            </dd>
          </div>
        </dl>
      </Card>

      {/* Open ports */}
      <h2 className="mb-3 text-lg font-semibold">Open Ports</h2>
      <Card padding="none" className="mb-6">
        {device.ports.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-[var(--color-text-secondary)]">
            No open ports recorded.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Open ports table">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-text-secondary)]">
                  <th scope="col" className="px-4 py-3">
                    Port
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Protocol
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Service
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Banner
                  </th>
                </tr>
              </thead>
              <tbody>
                {device.ports.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface)]"
                  >
                    <td className="px-4 py-2 font-mono">{p.port_number}</td>
                    <td className="px-4 py-2 uppercase text-[var(--color-text-secondary)]">
                      {p.protocol}
                    </td>
                    <td className="px-4 py-2">{p.service_name ?? "—"}</td>
                    <td className="px-4 py-2 font-mono text-xs text-[var(--color-text-secondary)]">
                      {p.version_banner ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Risks + Remediations paired side by side */}
      <div className="mb-2 flex items-baseline gap-3">
        <h2 className="text-lg font-semibold">Risks &amp; Remediations</h2>
        {!risksLoading && !recsLoading && (
          <span className="text-sm text-[var(--color-text-secondary)]">
            {sortedRisks.length} risk{sortedRisks.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {risksLoading || recsLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <SkeletonCard key={i} height="20" />
          ))}
        </div>
      ) : sortedRisks.length === 0 && orphanRecs.length === 0 ? (
        <Card>
          <p className="py-4 text-center text-sm text-[var(--color-text-secondary)]">
            No risks or recommendations for this device.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {/* Header row for desktop */}
          {sortedRisks.length > 0 && (
            <div className="hidden lg:grid lg:grid-cols-2 lg:gap-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Risk
              </p>
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Remediation
              </p>
            </div>
          )}
          {sortedRisks.map((risk) => (
            <RiskRecPair
              key={risk.id}
              risk={risk}
              rec={recByRiskId.get(risk.id)}
            />
          ))}
          {/* Orphan recommendations not linked to any discovered risk */}
          {orphanRecs.length > 0 && (
            <>
              <h3 className="mt-2 text-sm font-semibold text-[var(--color-text-secondary)]">
                Additional Recommendations
              </h3>
              {orphanRecs.map((rec) => (
                <RecCard key={rec.id} rec={rec} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
