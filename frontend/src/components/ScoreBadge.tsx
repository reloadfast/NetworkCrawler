/**
 * ScoreBadge — displays a device's 0–100 security score with colour coding.
 * ≥70 green, 40–69 amber, <40 red.
 */
interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}

function scoreColour(score: number): string {
  if (score >= 70)
    return "text-[var(--color-accent-positive)] border-[var(--color-accent-positive)]/40 bg-[var(--color-accent-positive)]/10";
  if (score >= 40)
    return "text-[var(--color-accent-warning)] border-[var(--color-accent-warning)]/40 bg-[var(--color-accent-warning)]/10";
  return "text-[var(--color-accent-danger)] border-[var(--color-accent-danger)]/40 bg-[var(--color-accent-danger)]/10";
}

const sizeClasses = {
  sm: "text-xs px-1.5 py-0.5 min-w-[2.25rem]",
  md: "text-sm px-2 py-1 min-w-[2.75rem]",
  lg: "text-base px-3 py-1.5 min-w-[3.5rem] font-semibold",
};

export function ScoreBadge({
  score,
  size = "md",
  className = "",
}: ScoreBadgeProps) {
  return (
    <span
      title={`Security score: ${score}/100`}
      className={[
        "inline-flex items-center justify-center rounded-full border font-mono font-medium",
        sizeClasses[size],
        scoreColour(score),
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {score}
    </span>
  );
}
