/**
 * ScanBanner — top-of-page banner shown while a scan is in progress.
 * It pulses gently to indicate activity and shows the current stage + elapsed time.
 */
import { useEffect, useState } from "react";

const STAGE_LABELS: Record<string, string> = {
  scanning: "Scanning network…",
  analysing: "Analysing risks…",
};

function useElapsed(startedAt: string | null | undefined): string {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startedAt) return;
    const origin = new Date(startedAt).getTime();
    const tick = () =>
      setElapsed(Math.max(0, Math.floor((Date.now() - origin) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export interface ScanBannerProps {
  scanId?: number | null;
  currentStage?: string | null;
  startedAt?: string | null;
}

export function ScanBanner({
  scanId,
  currentStage,
  startedAt,
}: ScanBannerProps) {
  const elapsed = useElapsed(startedAt);
  const stageLabel =
    (currentStage && STAGE_LABELS[currentStage]) ?? "Scan in progress";

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
        {stageLabel}
        {scanId != null && (
          <span className="ml-1 font-mono text-xs opacity-70">#{scanId}</span>
        )}
      </span>
      <span
        className="ml-auto font-mono text-xs opacity-70"
        aria-label={`Elapsed ${elapsed}`}
      >
        {elapsed}
      </span>
    </div>
  );
}
