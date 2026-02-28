/**
 * useToast — manages a list of toast notifications.
 * Kept in hooks/ so Toast.tsx only exports components (react-refresh compatible).
 */
import { useState } from 'react'
import type { ToastMessage, ToastVariant } from '../components/Toast'

export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = (message: string, variant: ToastVariant = 'info') => {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((prev) => [...prev, { id, message, variant }])
  }

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return { toasts, addToast, dismissToast }
}
