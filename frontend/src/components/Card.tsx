/**
 * Card — a surface container with rounded corners, subtle border, and
 * optional padding.  Uses the `surface` and `border` CSS tokens so it
 * responds automatically to the active theme.
 */
import React from 'react'

export interface CardProps {
  children: React.ReactNode
  /** Extra Tailwind classes forwarded to the wrapper element */
  className?: string
  /** Padding preset.  Defaults to 'md'. */
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Optional click handler */
  onClick?: React.MouseEventHandler<HTMLDivElement>
  /** Optional ARIA role */
  role?: React.AriaRole
}

const paddingMap: Record<NonNullable<CardProps['padding']>, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
}

export function Card({ children, className = '', padding = 'md', onClick, role }: CardProps) {
  return (
    <div
      className={[
        'rounded-xl border bg-surface',
        'border-[var(--color-border)]',
        'shadow-sm',
        paddingMap[padding],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onClick}
      role={role}
    >
      {children}
    </div>
  )
}
