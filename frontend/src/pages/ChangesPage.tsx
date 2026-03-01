/**
 * ChangesPage — timeline of network changes detected between scans.
 * Route: /changes
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, Badge, PageHeader } from "../components";
import { useChanges } from "../hooks/useChanges";
import type { ScanEvent } from "../types/api";

const EVENT_META: Record<
  ScanEvent["event_type"],
  {
    label: string;
    icon: string;
    variant: "critical" | "high" | "medium" | "neutral" | "positive";
  }
> = {
  device_appeared: { label: "New device", icon: "📡", variant: "medium" },
  device_disappeared: {
    label: "Device offline",
    icon: "🔌",
    variant: "neutral",
  },
  port_opened: { label: "Port opened", icon: "🔓", variant: "high" },
  port_closed: { label: "Port closed", icon: "🔒", variant: "neutral" },
  risk_appeared: { label: "New risk", icon: "⚠️", variant: "critical" },
  risk_resolved: { label: "Risk resolved", icon: "✅", variant: "positive" },
};

function parseDetail(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function EventDetail({ event }: { event: ScanEvent }) {
  const d = parseDetail(event.detail);
  switch (event.event_type) {
    case "device_appeared":
    case "device_disappeared":
      return (
        <span>
          <span className="font-mono">{String(d.ip ?? "")}</span>
          {d.hostname ? <> · {String(d.hostname)}</> : null}
          {d.vendor ? <> · {String(d.vendor)}</> : null}
          {d.label ? <> · "{String(d.label)}"</> : null}
        </span>
      );
    case "port_opened":
    case "port_closed":
      return (
        <span>
          <span className="font-mono">
            {String(d.port ?? "")}/{String(d.protocol ?? "")}
          </span>
          {d.service ? <> · {String(d.service)}</> : null}
        </span>
      );
    case "risk_appeared":
    case "risk_resolved":
      return (
        <span>
          {String(d.title ?? "")}
          {d.severity ? (
            <>
              {" "}
              · <span className="font-mono text-xs">{String(d.severity)}</span>
            </>
          ) : null}
        </span>
      );
    default:
      return <span>{event.detail ?? ""}</span>;
  }
}

function EventRow({
  event,
  onDismiss,
}: {
  event: ScanEvent;
  onDismiss: (id: number) => void;
}) {
  const meta = EVENT_META[event.event_type] ?? {
    label: event.event_type,
    icon: "•",
    variant: "neutral" as const,
  };

  return (
    <div
      className={[
        "flex items-start gap-3 px-4 py-3 border-b border-[var(--color-border)] last:border-0",
        event.reviewed ? "opacity-50" : "",
      ].join(" ")}
    >
      <span className="mt-0.5 text-base" aria-hidden="true">
        {meta.icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-0.5">
          <Badge
            variant={meta.variant === "positive" ? "neutral" : meta.variant}
          >
            {meta.label}
          </Badge>
          {event.device_id && (
            <Link
              to={`/devices/${event.device_id}`}
              className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:underline"
            >
              device #{event.device_id}
            </Link>
          )}
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">
          <EventDetail event={event} />
        </p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <time
          className="text-xs text-[var(--color-text-secondary)] whitespace-nowrap"
          dateTime={event.occurred_at ?? undefined}
        >
          {event.occurred_at
            ? new Date(event.occurred_at).toLocaleString()
            : "—"}
        </time>
        {!event.reviewed && (
          <button
            onClick={() => onDismiss(event.id)}
            aria-label="Mark as reviewed"
            title="Dismiss"
            className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

export function ChangesPage() {
  const [showReviewed, setShowReviewed] = useState(false);
  const { events, loading, markReviewed, markAllReviewed } = useChanges(
    showReviewed ? {} : { reviewed: false },
  );

  const unreviewedCount = events.filter((e) => !e.reviewed).length;

  // Group events by scan_id
  const grouped = events.reduce<Map<number, ScanEvent[]>>((acc, e) => {
    const list = acc.get(e.scan_id) ?? [];
    list.push(e);
    acc.set(e.scan_id, list);
    return acc;
  }, new Map());

  return (
    <div className="page-enter">
      <PageHeader
        title="Changes"
        subtitle="Network changes detected between scans"
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowReviewed((v) => !v)}
              className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
            >
              {showReviewed ? "Hide reviewed" : "Show all"}
            </button>
            {unreviewedCount > 0 && (
              <button
                onClick={() => void markAllReviewed()}
                className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
              >
                Dismiss all ({unreviewedCount})
              </button>
            )}
          </div>
        }
      />

      {loading ? (
        <Card>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-10 animate-pulse rounded bg-[var(--color-border)]"
              />
            ))}
          </div>
        </Card>
      ) : events.length === 0 ? (
        <Card>
          <p className="py-8 text-center text-sm text-[var(--color-text-secondary)]">
            {showReviewed
              ? "No change events recorded yet."
              : "No unreviewed changes — you're up to date."}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {Array.from(grouped.entries()).map(([scanId, scanEvents]) => (
            <Card key={scanId} padding="none">
              <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
                <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
                  Scan #{scanId}
                </span>
                <span className="text-xs text-[var(--color-text-secondary)]">
                  {scanEvents.length} event{scanEvents.length !== 1 ? "s" : ""}
                </span>
              </div>
              {scanEvents.map((e) => (
                <EventRow
                  key={e.id}
                  event={e}
                  onDismiss={(id) => void markReviewed(id)}
                />
              ))}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
