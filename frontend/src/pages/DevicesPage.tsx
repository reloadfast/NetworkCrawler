/**
 * DevicesPage — sortable/filterable table of all discovered devices.
 * Route: /devices
 */
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Badge, SkeletonTable, PageHeader, ScoreBadge } from "../components";
import { useDevices, useRisks } from "../hooks";
import type { Device } from "../types/api";

/** Inline label editor that saves on blur or Enter, cancels on Escape. */
function LabelCell({
  device,
  onSaved,
}: {
  device: Device;
  onSaved: (label: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(device.label ?? "");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const display = device.label ?? device.hostname ?? "—";
  const isPlaceholder = !device.label && !device.hostname;

  const startEdit = () => {
    setDraft(device.label ?? "");
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const save = () => {
    setSaving(true);
    const newLabel = draft.trim() || null;
    fetch(`/api/devices/${device.id}/label`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel }),
    })
      .then((r) => r.json())
      .then((d: Device) => onSaved(d.label))
      .catch(() => {})
      .finally(() => {
        setSaving(false);
        setEditing(false);
      });
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            inputRef.current?.blur();
          } else if (e.key === "Escape") {
            setEditing(false);
          }
        }}
        disabled={saving}
        className="w-full rounded border border-[var(--color-accent-primary)] bg-[var(--color-background)] px-1.5 py-0.5 text-sm text-[var(--color-text-primary)] focus:outline-none"
        placeholder="Add label…"
      />
    );
  }

  return (
    <span className="group flex items-center gap-1.5">
      <span
        className={
          isPlaceholder ? "text-[var(--color-text-secondary)]" : undefined
        }
      >
        {display}
      </span>
      <button
        onClick={startEdit}
        aria-label={`Edit label for ${device.ip_address}`}
        title="Edit label"
        className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-xs transition-opacity"
      >
        ✏
      </button>
    </span>
  );
}

type SortKey =
  | "ip_address"
  | "hostname"
  | "os_guess"
  | "ports"
  | "risks"
  | "score"
  | "last_seen";
type SortDir = "asc" | "desc";

function sortDevices(
  devices: Device[],
  riskCounts: Record<number, number>,
  key: SortKey,
  dir: SortDir,
): Device[] {
  return [...devices].sort((a, b) => {
    let av: string | number = 0;
    let bv: string | number = 0;
    switch (key) {
      case "ip_address":
        av = a.ip_address;
        bv = b.ip_address;
        break;
      case "hostname":
        av = a.hostname ?? "";
        bv = b.hostname ?? "";
        break;
      case "os_guess":
        av = a.os_guess ?? "";
        bv = b.os_guess ?? "";
        break;
      case "ports":
        av = a.ports.length;
        bv = b.ports.length;
        break;
      case "risks":
        av = riskCounts[a.id] ?? 0;
        bv = riskCounts[b.id] ?? 0;
        break;
      case "score":
        av = a.security_score;
        bv = b.security_score;
        break;
      case "last_seen":
        av = a.last_seen ?? "";
        bv = b.last_seen ?? "";
        break;
    }
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

export function DevicesPage() {
  const { devices: rawDevices, loading, error } = useDevices();
  const [localLabels, setLocalLabels] = useState<Record<number, string | null>>(
    {},
  );
  const devices = useMemo(
    () =>
      rawDevices.map((d) =>
        d.id in localLabels ? { ...d, label: localLabels[d.id] } : d,
      ),
    [rawDevices, localLabels],
  );
  const { risks } = useRisks();
  const [filter, setFilter] = useState("");
  const [osFilter, setOsFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("ip_address");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const riskCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const r of risks) {
      counts[r.device_id] = (counts[r.device_id] ?? 0) + 1;
    }
    return counts;
  }, [risks]);

  const osOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const d of devices) {
      if (d.os_guess) seen.add(d.os_guess);
    }
    return Array.from(seen).sort();
  }, [devices]);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return devices.filter(
      (d) =>
        (d.ip_address.includes(q) ||
          (d.hostname ?? "").toLowerCase().includes(q) ||
          (d.mac_address ?? "").toLowerCase().includes(q) ||
          (d.os_guess ?? "").toLowerCase().includes(q)) &&
        (osFilter === "" || d.os_guess === osFilter),
    );
  }, [devices, filter, osFilter]);

  const sorted = useMemo(
    () => sortDevices(filtered, riskCounts, sortKey, sortDir),
    [filtered, riskCounts, sortKey, sortDir],
  );

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? (sortDir === "asc" ? " ▲" : " ▼") : " ⬍";

  return (
    <div>
      <PageHeader
        title="Devices"
        subtitle={
          devices.length > 0
            ? `${devices.length} device${devices.length !== 1 ? "s" : ""} discovered`
            : undefined
        }
        action={
          <div className="flex flex-wrap gap-2">
            <input
              type="search"
              placeholder="Filter by IP, hostname, OS…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="Filter devices"
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)] sm:w-56"
            />
            {osOptions.length > 0 && (
              <select
                value={osFilter}
                onChange={(e) => setOsFilter(e.target.value)}
                aria-label="Filter by OS"
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
              >
                <option value="">All OS</option>
                {osOptions.map((os) => (
                  <option key={os} value={os}>
                    {os}
                  </option>
                ))}
              </select>
            )}
          </div>
        }
      />

      {loading && <SkeletonTable rows={6} />}
      {error && (
        <p className="text-[var(--color-accent-danger)]">Error: {error}</p>
      )}

      {!loading && !error && devices.length === 0 && (
        <Card>
          <p className="py-8 text-center text-[var(--color-text-secondary)]">
            No devices discovered yet. Trigger a scan from the Dashboard.
          </p>
        </Card>
      )}

      {!loading && !error && devices.length > 0 && (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Devices table">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-text-secondary)]">
                  {(
                    [
                      ["ip_address", "IP Address"],
                      ["hostname", "Hostname"],
                      ["os_guess", "OS"],
                      ["ports", "Ports"],
                      ["risks", "Risks"],
                      ["score", "Score"],
                      ["last_seen", "Last Seen"],
                    ] as [SortKey, string][]
                  ).map(([key, label]) => (
                    <th
                      key={key}
                      scope="col"
                      className="cursor-pointer select-none px-4 py-3 hover:text-[var(--color-text-primary)]"
                      onClick={() => handleSort(key)}
                      aria-sort={
                        sortKey === key
                          ? sortDir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      {label}
                      <SortIcon k={key} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-8 text-center text-[var(--color-text-secondary)]"
                    >
                      No devices match the filter.
                    </td>
                  </tr>
                )}
                {sorted.map((device) => (
                  <tr
                    key={device.id}
                    className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface)]"
                  >
                    <td className="px-4 py-3 font-mono">
                      <Link
                        to={`/devices/${device.id}`}
                        className="text-[var(--color-accent-positive)] hover:underline"
                      >
                        {device.ip_address}
                      </Link>
                      {device.trusted && (
                        <span
                          title="Trusted device"
                          aria-label="Trusted device"
                          className="ml-1.5 text-xs opacity-60"
                        >
                          🛡
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                      <LabelCell
                        device={device}
                        onSaved={(label) =>
                          setLocalLabels((prev) => ({
                            ...prev,
                            [device.id]: label,
                          }))
                        }
                      />
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                      {device.os_guess ?? "—"}
                    </td>
                    <td className="px-4 py-3">{device.ports.length}</td>
                    <td className="px-4 py-3">
                      {riskCounts[device.id] ? (
                        <Badge variant="high">{riskCounts[device.id]}</Badge>
                      ) : (
                        <Badge variant="neutral">0</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={device.security_score} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                      {device.last_seen
                        ? new Date(device.last_seen).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
