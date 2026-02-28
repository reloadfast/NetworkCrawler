/**
 * DevicesPage — sortable/filterable table of all discovered devices.
 * Route: /devices
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Badge, SkeletonTable } from "../components";
import { useDevices, useRisks } from "../hooks";
import type { Device } from "../types/api";

type SortKey =
  | "ip_address"
  | "hostname"
  | "os_guess"
  | "ports"
  | "risks"
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
  const { devices, loading, error } = useDevices();
  const { risks } = useRisks();
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("ip_address");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const riskCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const r of risks) {
      counts[r.device_id] = (counts[r.device_id] ?? 0) + 1;
    }
    return counts;
  }, [risks]);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return devices.filter(
      (d) =>
        d.ip_address.includes(q) ||
        (d.hostname ?? "").toLowerCase().includes(q) ||
        (d.mac_address ?? "").toLowerCase().includes(q) ||
        (d.os_guess ?? "").toLowerCase().includes(q),
    );
  }, [devices, filter]);

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
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Devices</h1>
        <input
          type="search"
          placeholder="Filter by IP, hostname, OS…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter devices"
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-positive)] sm:w-64"
        />
      </div>

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
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                      {device.hostname ?? "—"}
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
