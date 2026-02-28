/**
 * RecommendationsPage — sortable list of all hardening recommendations.
 * Route: /recommendations
 */
import { memo, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Badge, SkeletonCard } from "../components";
import { useRecommendations } from "../hooks";
import type { Recommendation, Severity } from "../types/api";

type SortKey = "severity" | "effort" | "impact";

const SEV_ORDER: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};
const EFFORT_ORDER: Record<string, number> = { low: 0, medium: 1, high: 2 };
const IMPACT_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function chipClass(value: string): string {
  switch (value) {
    case "critical":
      return "bg-[var(--color-accent-danger)] text-white";
    case "high":
      return "bg-[var(--color-accent-warning)] text-black";
    case "medium":
      return "bg-[var(--color-accent-caution)] text-black";
    case "low":
      return "bg-[var(--color-accent-info)] text-white";
    default:
      return "bg-[var(--color-surface)] text-[var(--color-text-secondary)]";
  }
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${chipClass(value)}`}
      aria-label={`${label}: ${value}`}
    >
      {label}: {value}
    </span>
  );
}

export function RecommendationsPage() {
  const { recommendations, loading, error } = useRecommendations();
  const [sortKey, setSortKey] = useState<SortKey>("severity");

  const sorted = useMemo(() => {
    return [...recommendations].sort((a, b) => {
      switch (sortKey) {
        case "severity":
          return (SEV_ORDER[a.severity] ?? 99) - (SEV_ORDER[b.severity] ?? 99);
        case "effort":
          return (
            (EFFORT_ORDER[a.effort] ?? 99) - (EFFORT_ORDER[b.effort] ?? 99)
          );
        case "impact":
          return (
            (IMPACT_ORDER[a.impact] ?? 99) - (IMPACT_ORDER[b.impact] ?? 99)
          );
        default:
          return 0;
      }
    });
  }, [recommendations, sortKey]);

  if (loading)
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} height="24" />
        ))}
      </div>
    );
  if (error)
    return <p className="text-[var(--color-accent-danger)]">Error: {error}</p>;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Recommendations</h1>
        <div className="flex items-center gap-2">
          <label
            htmlFor="sort-select"
            className="text-sm text-[var(--color-text-secondary)]"
          >
            Sort by:
          </label>
          <select
            id="sort-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            aria-label="Sort recommendations"
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-sm text-[var(--color-text-primary)] focus:outline-none"
          >
            <option value="severity">Severity</option>
            <option value="effort">Effort</option>
            <option value="impact">Impact</option>
          </select>
        </div>
      </div>

      {sorted.length === 0 ? (
        <Card>
          <p className="py-8 text-center text-sm text-[var(--color-text-secondary)]">
            No recommendations yet. Run a scan to generate hardening advice.
          </p>
        </Card>
      ) : (
        <div
          className="flex flex-col gap-3"
          role="list"
          aria-label="Recommendations list"
        >
          {sorted.map((rec) => (
            <RecommendationRow key={rec.id} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}

const RecommendationRow = memo(function RecommendationRow({
  rec,
}: {
  rec: Recommendation;
}) {
  return (
    <Card role="listitem">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Badge variant={rec.severity}>{rec.severity}</Badge>
            <Link
              to={`/recommendations/${rec.id}`}
              className="font-medium hover:underline text-[var(--color-text-primary)]"
              aria-label={`View details for ${rec.title}`}
            >
              {rec.title}
            </Link>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2">
            {rec.description}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip label="Effort" value={rec.effort} />
            <Chip label="Impact" value={rec.impact} />
          </div>
        </div>
        <div className="text-right shrink-0">
          <Link
            to={`/devices/${rec.device_id}`}
            className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            Device #{rec.device_id}
          </Link>
        </div>
      </div>
    </Card>
  );
});
