import { createContext, useContext } from 'react'
import type { ToastMessage } from 'primereact/toast'

export interface ToastApi {
  show: (message: ToastMessage | ToastMessage[]) => void
  clear: () => void
}

export const ToastContext = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (ctx === null) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}