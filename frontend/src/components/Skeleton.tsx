/**
 * Skeleton — animated placeholder blocks shown while content is loading.
 * Uses the `.skeleton` CSS class (shimmer animation) from theme.css.
 */

export interface SkeletonProps {
  /** Number of rows to render */
  rows?: number;
  /** Height of each row in Tailwind units (e.g. '4', '6') */
  height?: string;
  /** Extra Tailwind classes forwarded to each row */
  className?: string;
}

export function Skeleton({
  rows = 3,
  height = "4",
  className = "",
}: SkeletonProps) {
  return (
    <div
      className="flex flex-col gap-3"
      role="status"
      aria-label="Loading"
      aria-busy="true"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`skeleton h-${height} w-full ${className}`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

/** A skeleton row that mimics a card (rounded, full-width) */
export function SkeletonCard({ height = "20" }: { height?: string }) {
  return (
    <div
      className={`skeleton h-${height} w-full rounded-xl`}
      role="status"
      aria-label="Loading"
      aria-busy="true"
    />
  );
}

/** A skeleton table — header + N body rows */
export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div
      className="rounded-xl border border-[var(--color-border)] overflow-hidden"
      role="status"
      aria-label="Loading"
      aria-busy="true"
    >
      {/* Fake header */}
      <div className="skeleton h-10 w-full rounded-none" aria-hidden="true" />
      {/* Fake rows */}
      <div className="flex flex-col">
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="skeleton h-12 w-full rounded-none border-t border-[var(--color-border)]"
            aria-hidden="true"
          />
        ))}
      </div>
    </div>
  );
}
