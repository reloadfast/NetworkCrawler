/**
 * DeviceDetailPage — ports/services table, risk list, timestamps.
 * Route: /devices/:id
 */
import { memo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Card, Badge, SkeletonCard } from '../components'
import { useDevice, useRisks, useDeviceRecommendations } from '../hooks'
import type { Risk, Recommendation, Severity } from '../types/api'

const SEV_ORDER: Severity[] = ['critical', 'high', 'medium', 'low']

const RiskCard = memo(function RiskCard({ risk }: { risk: Risk }) {
  return (
    <Card>
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
  )
})

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
      <p className="text-sm text-[var(--color-text-secondary)]">{rec.description}</p>
    </Card>
  )
})

export function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const deviceId = Number(id)
  const { device, loading, error } = useDevice(deviceId)
  const { risks, loading: risksLoading } = useRisks({ deviceId })
  const { recommendations, loading: recsLoading } = useDeviceRecommendations(deviceId)

  if (loading) return <SkeletonCard height="48" />
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
                  <th scope="col" className="px-4 py-3">Port</th>
                  <th scope="col" className="px-4 py-3">Protocol</th>
                  <th scope="col" className="px-4 py-3">Service</th>
                  <th scope="col" className="px-4 py-3">Banner</th>
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
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <SkeletonCard key={i} height="20" />
          ))}
        </div>
      ) : sortedRisks.length === 0 ? (
        <Card>
          <p className="py-4 text-center text-sm text-[var(--color-text-secondary)]">
            No risks detected for this device.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {sortedRisks.map((risk) => (
            <RiskCard key={risk.id} risk={risk} />
          ))}
        </div>
      )}

      {/* Recommendations */}
      <h2 className="mb-3 mt-6 text-lg font-semibold">
        Recommendations{' '}
        {!recsLoading && (
          <span className="text-base font-normal text-[var(--color-text-secondary)]">
            ({recommendations.length})
          </span>
        )}
      </h2>
      {recsLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <SkeletonCard key={i} height="20" />
          ))}
        </div>
      ) : recommendations.length === 0 ? (
        <Card>
          <p className="py-4 text-center text-sm text-[var(--color-text-secondary)]">
            No recommendations for this device.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {recommendations.map((rec) => (
            <RecCard key={rec.id} rec={rec} />
          ))}
        </div>
      )}
    </div>
  )
}
