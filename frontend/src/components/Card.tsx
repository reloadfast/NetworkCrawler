/**
 * Card — a surface container with rounded corners, subtle border, and
 * optional padding.  Uses the `surface` and `border` CSS tokens so it
 * responds automatically to the active theme.
 *
 * When `onClick` is provided the card is rendered as a keyboard-accessible
 * interactive element: it receives `tabIndex={0}`, a `cursor-pointer` style,
 * and responds to Enter/Space key events.
 */
import React from 'react'

export interface CardProps {
  children: React.ReactNode
  /** Extra Tailwind classes forwarded to the wrapper element */
  className?: string
  /** Padding preset.  Defaults to 'md'. */
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Optional click handler — makes the card keyboard-interactive */
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
  const isInteractive = Boolean(onClick)

  const handleKeyDown = isInteractive
    ? (e: React.KeyboardEvent<HTMLDivElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          // Synthesise a click so onClick fires
          e.currentTarget.click()
        }
      }
    : undefined

  return (
    <div
      className={[
        'rounded-xl border bg-surface',
        'border-[var(--color-border)]',
        'shadow-sm',
        paddingMap[padding],
        isInteractive ? 'cursor-pointer' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={role}
      tabIndex={isInteractive ? 0 : undefined}
    >
      {children}
    </div>
  )
}
