/**
 * Renders the single PrimeReact Toast singleton and exposes ``show``/``clear``
 * to the rest of the tree via ``ToastContext``. Wrapped around the routes in
 * ``App.tsx``; pages call ``useToast()`` (see ``ToastContext.ts`` for the
 * contract).
 */
import { useCallback, useRef, type ReactNode } from 'react'
import { Toast } from 'primereact/toast'
import { ToastContext, type ToastApi } from './ToastContext'

function ToastProvider({ children }: { children: ReactNode }) {
  const toastRef = useRef<Toast>(null)

  const show = useCallback<ToastApi['show']>((message) => {
    toastRef.current?.show(message)
  }, [])

  const clear = useCallback<ToastApi['clear']>(() => {
    toastRef.current?.clear()
  }, [])

  return (
    <ToastContext.Provider value={{ show, clear }}>
      <Toast ref={toastRef} />
      {children}
    </ToastContext.Provider>
  )
}

export default ToastProvider