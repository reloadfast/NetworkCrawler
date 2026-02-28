/**
 * DeviceDetailPage — ports/services table, risk list, timestamps.
 * Route: /devices/:id
 */
import { Link, useParams } from 'react-router-dom'
import { Card, Badge } from '../components'
import { useDevice, useRisks } from '../hooks'
import type { Severity } from '../types/api'

const SEV_ORDER: Severity[] = ['critical', 'high', 'medium', 'low']

export function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const deviceId = Number(id)
  const { device, loading, error } = useDevice(deviceId)
  const { risks, loading: risksLoading } = useRisks({ deviceId })

  if (loading) return <p className="text-[var(--color-text-secondary)]">Loading…</p>
  if (error) return <p className="text-[var(--color-accent-danger)]">Error: {error}</p>
  if (!device) return <p className="text-[var(--color-text-secondary)]">Device not found.</p>

  const sortedRisks = [...risks].sort(
    (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity),
  )

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <Link
          to="/devices"
          className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >
          ← Devices
        </Link>
        <span className="text-[var(--color-border)]">/</span>
        <h1 className="text-2xl font-bold tracking-tight font-mono">{device.ip_address}</h1>
      </div>

      {/* Device metadata */}
      <Card className="mb-6">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {[
            ['Hostname', device.hostname ?? '—'],
            ['MAC Address', device.mac_address ?? '—'],
            ['Vendor', device.vendor ?? '—'],
            ['OS', device.os_guess ?? '—'],
            ['First Seen', device.first_seen ? new Date(device.first_seen).toLocaleString() : '—'],
            ['Last Seen', device.last_seen ? new Date(device.last_seen).toLocaleString() : '—'],
          ].map(([label, value]) => (
            <div key={label} className="flex flex-col">
              <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                {label}
              </dt>
              <dd className="font-mono text-[var(--color-text-primary)]">{value}</dd>
            </div>
          ))}
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
                  <th className="px-4 py-3">Port</th>
                  <th className="px-4 py-3">Protocol</th>
                  <th className="px-4 py-3">Service</th>
                  <th className="px-4 py-3">Banner</th>
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
                    <td className="px-4 py-2">{p.service_name ?? '—'}</td>
                    <td className="px-4 py-2 font-mono text-xs text-[var(--color-text-secondary)]">
                      {p.version_banner ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Risks */}
      <h2 className="mb-3 text-lg font-semibold">
        Risks{' '}
        {!risksLoading && (
          <span className="text-base font-normal text-[var(--color-text-secondary)]">
            ({sortedRisks.length})
          </span>
        )}
      </h2>
      {risksLoading ? (
        <p className="text-[var(--color-text-secondary)]">Loading risks…</p>
      ) : sortedRisks.length === 0 ? (
        <Card>
          <p className="py-4 text-center text-sm text-[var(--color-text-secondary)]">
            No risks detected for this device.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {sortedRisks.map((risk) => (
            <Card key={risk.id}>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <Badge variant={risk.severity}>{risk.severity}</Badge>
                <span className="font-medium">{risk.title}</span>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)]">{risk.description}</p>
              <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
                Check: <span className="font-mono">{risk.check_id}</span>
                {risk.detected_at && (
                  <> &middot; Detected {new Date(risk.detected_at).toLocaleString()}</>
                )}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
