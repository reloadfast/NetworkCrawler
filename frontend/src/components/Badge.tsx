/**
 * Badge — a small inline label for severity levels, statuses, or tags.
 * Colour variant maps to the four-tier risk model and theme tokens.
 */
import React from 'react'

export type BadgeVariant = 'critical' | 'high' | 'medium' | 'low' | 'neutral'

export interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  critical: 'bg-[var(--color-accent-danger)]/15 text-[var(--color-accent-danger)] border-[var(--color-accent-danger)]/30',
  high:     'bg-[var(--color-accent-danger)]/10 text-[var(--color-accent-danger)] border-[var(--color-accent-danger)]/20',
  medium:   'bg-[var(--color-accent-warning)]/15 text-[var(--color-accent-warning)] border-[var(--color-accent-warning)]/30',
  low:      'bg-[var(--color-accent-positive)]/15 text-[var(--color-accent-positive)] border-[var(--color-accent-positive)]/30',
  neutral:  'bg-[var(--color-border)]/40 text-[var(--color-text-secondary)] border-[var(--color-border)]',
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-2 py-0.5',
        'text-xs font-medium tracking-wide uppercase',
        variantClasses[variant],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </span>
  )
}
