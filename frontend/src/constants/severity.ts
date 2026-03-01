/**
 * Shared severity constants — single source of truth for ordering,
 * colours, and label lists used across pages and components.
 */
import type { Severity } from "../types/api";

/** Ordered from most to least severe. */
export const SEV_LEVELS: Severity[] = ["critical", "high", "medium", "low"];

/** Map severity → CSS colour variable. */
export const SEV_COLORS: Record<Severity, string> = {
  critical: "var(--color-accent-danger)",
  high: "var(--color-accent-warning)",
  medium: "var(--color-accent-caution)",
  low: "var(--color-accent-positive)",
} as const;

/** Map severity → sort rank (lower = more severe). */
export const SEV_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
} as const;
