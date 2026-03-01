/**
 * RecommendationDetailPage — full recommendation with numbered steps,
 * effort/impact indicators, expandable exploitation context, and link back to device.
 * Route: /recommendations/:id
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, Badge, SkeletonCard } from "../components";
import { useRecommendations } from "../hooks";

function EffortImpactBar({ label, value }: { label: string; value: string }) {
  const filled =
    value === "low" ? 1 : value === "medium" ? 2 : value === "critical" ? 4 : 3;
  return (
    <div className="flex items-center gap-2" aria-label={`${label}: ${value}`}>
      <span className="w-14 text-xs text-[var(--color-text-secondary)]">
        {label}
      </span>
      <div className="flex gap-1" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-2 w-6 rounded-sm ${
              i <= filled
                ? "bg-[var(--color-accent-primary)]"
                : "bg-[var(--color-border)]"
            }`}
          />
        ))}
      </div>
      <span className="text-xs capitalize text-[var(--color-text-secondary)]">
        {value}
      </span>
    </div>
  );
}

function ExpandableSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left hover:bg-[var(--color-surface-hover)] transition-colors"
        aria-expanded={open}
      >
        <span>{title}</span>
        <span
          className={`text-[var(--color-text-secondary)] transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          ▾
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 text-sm text-[var(--color-text-secondary)] leading-relaxed border-t border-[var(--color-border)]">
          {children}
        </div>
      )}
    </div>
  );
}

export function RecommendationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const recId = Number(id);
  const { recommendations, loading, error } = useRecommendations();

  if (loading) return <SkeletonCard height="48" />;
  if (error)
    return <p className="text-[var(--color-accent-danger)]">Error: {error}</p>;

  const rec = recommendations.find((r) => r.id === recId);
  if (!rec) {
    return (
      <p className="text-[var(--color-text-secondary)]">
        Recommendation not found.
      </p>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-3">
        <Link
          to="/recommendations"
          className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >
          ← Recommendations
        </Link>
        <span className="text-[var(--color-border)]">/</span>
        <span className="text-sm truncate max-w-xs text-[var(--color-text-primary)]">
          {rec.title}
        </span>
      </div>

      {/* Header card */}
      <Card className="mb-6">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Badge variant={rec.severity}>{rec.severity}</Badge>
          <h1 className="text-xl font-bold">{rec.title}</h1>
        </div>
        <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
          {rec.description}
        </p>
        <div className="flex flex-col gap-2">
          <EffortImpactBar label="Effort" value={rec.effort} />
          <EffortImpactBar label="Impact" value={rec.impact} />
        </div>
        <div className="mt-4 border-t border-[var(--color-border)] pt-4">
          <span className="text-xs text-[var(--color-text-secondary)]">
            Check: <span className="font-mono">{rec.check_id}</span>
            {" · "}
            <Link to={`/devices/${rec.device_id}`} className="hover:underline">
              Device #{rec.device_id}
            </Link>
          </span>
        </div>
      </Card>

      {/* Remediation steps */}
      <h2 className="mb-3 text-lg font-semibold">Remediation Steps</h2>
      <Card className="mb-6">
        <ol className="flex flex-col gap-3">
          {rec.steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-primary)] text-xs font-bold text-white"
                aria-hidden="true"
              >
                {i + 1}
              </span>
              <span className="text-sm text-[var(--color-text-primary)]">
                {step}
              </span>
            </li>
          ))}
        </ol>
      </Card>

      {/* Contextual intelligence */}
      {(rec.attack_scenario || rec.likelihood) && (
        <div className="flex flex-col gap-3">
          {rec.attack_scenario && (
            <ExpandableSection title="🎯 How could this be exploited?">
              {rec.attack_scenario}
            </ExpandableSection>
          )}
          {rec.likelihood && (
            <ExpandableSection title="📊 How likely is this on a home network?">
              {rec.likelihood}
            </ExpandableSection>
          )}
        </div>
      )}
    </div>
  );
}
