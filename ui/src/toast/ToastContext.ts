/**
 * Global toast mechanism: the ``show`` / ``clear`` api pages receive via
 * ``useToast``. The context holds ``null`` outside the provider, so
 * ``useToast`` throws rather than letting pages silently render without
 * toasts.
 *
 * ``show`` accepts a single fully-formatted ToastMessage (severity, summary,
 * detail) or an array of them (e.g. the delete result success + warn pair in
 * FilesPage). ``clear`` dismisses every currently visible toast.
 */
import { createContext, useContext } from 'react'
import type { ToastMessage } from 'primereact/toast'

/** The toast api exposed through context: show message(s) or clear all. */
export interface ToastApi {
  show: (message: ToastMessage | ToastMessage[]) => void
  clear: () => void
}

export const ToastContext = createContext<ToastApi | null>(null)

/**
 * Get the toast api.
 *
 * Throws when called outside of ``ToastProvider`` so a missing provider is a
 * loud developer error instead of a silent no-op.
 */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (ctx === null) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}