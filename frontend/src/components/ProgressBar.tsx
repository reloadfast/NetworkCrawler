/**
 * ProgressBar — a horizontal bar showing a 0–100 percentage value.
 * Uses smooth rounded ends and a coloured fill driven by the theme tokens.
 */

export type ProgressBarVariant = "positive" | "warning" | "danger" | "neutral";

export interface ProgressBarProps {
  /** Value between 0 and 100 */
  value: number;
  variant?: ProgressBarVariant;
  /** Show the numeric percentage label beside the bar */
  showLabel?: boolean;
  /** Accessible label for screen readers */
  "aria-label"?: string;
  className?: string;
}

const variantColor: Record<ProgressBarVariant, string> = {
  positive: "var(--color-accent-positive)",
  warning: "var(--color-accent-warning)",
  danger: "var(--color-accent-danger)",
  neutral: "var(--color-text-secondary)",
};

export function ProgressBar({
  value,
  variant = "neutral",
  showLabel = false,
  "aria-label": ariaLabel,
  className = "",
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div
      className={["flex items-center gap-2", className]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={ariaLabel}
        className="relative h-2 flex-1 overflow-hidden rounded-full bg-[var(--color-border)]"
      >
        <div
          className="h-full rounded-full transition-[width] duration-200 ease-out"
          style={{
            width: `${clamped}%`,
            backgroundColor: variantColor[variant],
          }}
        />
      </div>
      {showLabel && (
        <span className="w-9 text-right text-xs text-[var(--color-text-secondary)]">
          {clamped}%
        </span>
      )}
    </div>
  );
}
