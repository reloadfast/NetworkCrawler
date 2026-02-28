/**
 * ScanBanner — top-of-page banner shown while a scan is in progress.
 * It pulses gently to indicate activity.
 */

export interface ScanBannerProps {
  scanId?: number | null;
}

export function ScanBanner({ scanId }: ScanBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Scan in progress"
      className={[
        "flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm font-medium mb-4",
        "border-[var(--color-accent-primary)]/40",
        "bg-[var(--color-accent-primary)]/10",
        "text-[var(--color-accent-primary)]",
      ].join(" ")}
    >
      {/* Pulsing dot */}
      <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-accent-primary)] opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--color-accent-primary)]" />
      </span>
      <span>
        Scan in progress
        {scanId != null && (
          <span className="ml-1 font-mono text-xs opacity-70">#{scanId}</span>
        )}
        … results will update automatically.
      </span>
    </div>
  );
}
