/**
 * Persisted color-scheme hook.
 *
 * The chosen mode (``'light' | 'dark' | 'system'``) is persisted under the
 * ``theme`` localStorage key (``STORAGE_KEY``). Initial state reads that key:
 * a valid stored value wins, otherwise it falls back to ``'system'``, which
 * resolves to the OS ``prefers-color-scheme`` preference. The resolved scheme
 * is applied by setting ``document.documentElement.dataset.theme`` to
 * ``'light'`` or ``'dark'`` (vite.config.ts scopes the PrimeReact dark
 * stylesheet to ``html[data-theme='dark']``, so this one attribute flips the
 * whole theme). While the mode is ``'system'``, OS color-scheme changes are
 * followed live; while a light/dark override is stored, they are ignored.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

/** localStorage key the selected theme mode is persisted under. */
const STORAGE_KEY = 'theme'
/** Media query that reports the OS light/dark preference. */
const DARK_QUERY = '(prefers-color-scheme: dark)'

/** Return the OS-preferred scheme ('dark' or 'light'), never a stored value. */
export function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
}

/**
 * Read the persisted theme mode from localStorage.
 *
 * Returns ``null`` when nothing is stored or the stored value is not a valid
 * ``ThemeMode``, so callers can treat "no override" and "bad override" the
 * same way (fall back to ``'system'``).
 */
export function getStoredTheme(): ThemeMode | null {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : null
}

/**
 * Resolve a theme mode to a concrete scheme.
 *
 * ``'light'``/``'dark'`` pass through; ``null`` and ``'system'`` resolve via
 * ``getSystemTheme``.
 */
export function resolveTheme(mode: ThemeMode | null): 'light' | 'dark' {
  return mode === 'light' || mode === 'dark' ? mode : getSystemTheme()
}

/**
 * Theme state hook: read/write the persisted mode and keep the applied
 * ``data-theme`` attribute in sync (including following OS changes in system
 * mode). Returns ``{ mode, resolved, setTheme, clearOverride }``.
 */
export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(() => getStoredTheme() ?? 'system')

  const apply = useCallback((next: 'light' | 'dark') => {
    document.documentElement.dataset.theme = next
  }, [])

  useEffect(() => {
    apply(resolveTheme(mode))
  }, [apply, mode])

  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY)
    const onChange = () => {
      if (mode === 'system') apply(getSystemTheme())
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [apply, mode])

  const setTheme = useCallback((next: ThemeMode) => {
    window.localStorage.setItem(STORAGE_KEY, next)
    setModeState(next)
  }, [])

  const clearOverride = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY)
    setModeState('system')
  }, [])

  const resolved = resolveTheme(mode)

  return useMemo(
    () => ({ mode, resolved, setTheme, clearOverride }),
    [clearOverride, mode, resolved, setTheme],
  )
}