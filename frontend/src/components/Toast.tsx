/**
 * Toast — temporary notification shown at the bottom of the screen.
 * Appears with an animation and auto-dismisses after `duration` ms.
 */
import { useEffect, useState } from 'react'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: string
  message: string
  variant: ToastVariant
}

interface ToastItemProps {
  toast: ToastMessage
  onDismiss: (id: string) => void
  duration?: number
}

const variantClass: Record<ToastVariant, string> = {
  success: 'bg-[var(--color-accent-positive)] text-white',
  error:   'bg-[var(--color-accent-danger)] text-white',
  info:    'bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border)]',
}

function ToastItem({ toast, onDismiss, duration = 4000 }: ToastItemProps) {
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true)
      setTimeout(() => onDismiss(toast.id), 220)
    }, duration)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss, duration])

  return (
    <div
      role="alert"
      aria-live="polite"
      className={[
        'flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg text-sm font-medium',
        'min-w-[240px] max-w-sm',
        variantClass[toast.variant],
        exiting ? 'toast-exit' : 'toast-enter',
      ].join(' ')}
    >
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>
  )
}

export interface ToastContainerProps {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
  duration?: number
}

export function ToastContainer({ toasts, onDismiss, duration }: ToastContainerProps) {
  if (toasts.length === 0) return null
  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} duration={duration} />
      ))}
    </div>
  )
}


