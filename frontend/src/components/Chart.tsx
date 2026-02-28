/**
 * Chart — a radial (donut) SVG chart for displaying a single percentage
 * metric (e.g. "devices at risk", "checks passed").
 *
 * Uses only SVG — no canvas, no third-party chart library.
 */
import React from "react";

export type ChartVariant = "positive" | "warning" | "danger" | "neutral";

export interface ChartProps {
  /** Value between 0 and 100 */
  value: number;
  variant?: ChartVariant;
  /** Size of the SVG in pixels.  Defaults to 80. */
  size?: number;
  /** Stroke width of the arc.  Defaults to 8. */
  strokeWidth?: number;
  /** Optional label rendered in the centre of the donut */
  label?: React.ReactNode;
  /** Accessible description */
  "aria-label"?: string;
  className?: string;
}

const variantColor: Record<ChartVariant, string> = {
  positive: "var(--color-accent-positive)",
  warning: "var(--color-accent-warning)",
  danger: "var(--color-accent-danger)",
  neutral: "var(--color-text-secondary)",
};

export function Chart({
  value,
  variant = "neutral",
  size = 80,
  strokeWidth = 8,
  label,
  "aria-label": ariaLabel,
  className = "",
}: ChartProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - clamped / 100);
  const center = size / 2;

  return (
    <div
      className={["relative inline-flex items-center justify-center", className]
        .filter(Boolean)
        .join(" ")}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-label={ariaLabel}
        role="img"
        style={{ transform: "rotate(-90deg)" }}
      >
        {/* Track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={strokeWidth}
        />
        {/* Fill */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={variantColor[variant]}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: "stroke-dashoffset 250ms ease-out" }}
        />
      </svg>
      {label !== undefined && (
        <div className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-[var(--color-text-primary)]">
          {label}
        </div>
      )}
    </div>
  );
}
