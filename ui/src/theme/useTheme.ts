import { useCallback, useEffect, useMemo, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

export function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
}

export function getStoredTheme(): ThemeMode | null {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : null
}

export function resolveTheme(mode: ThemeMode | null): 'light' | 'dark' {
  return mode === 'light' || mode === 'dark' ? mode : getSystemTheme()
}

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