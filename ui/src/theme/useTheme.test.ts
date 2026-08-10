import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resolveTheme, useTheme } from './useTheme'

const DARK_QUERY = '(prefers-color-scheme: dark)'
const STORAGE_KEY = 'theme'

type ChangeListener = () => void

function makeMatchMedia(initialDark: boolean) {
  let dark = initialDark
  const listeners = new Set<ChangeListener>()
  const mock = {
    media: DARK_QUERY,
    addEventListener: (_type: string, listener: ChangeListener) => {
      listeners.add(listener)
    },
    removeEventListener: (_type: string, listener: ChangeListener) => {
      listeners.delete(listener)
    },
    trigger(isDark: boolean) {
      dark = isDark
      listeners.forEach((listener) => listener())
    },
  }
  Object.defineProperty(mock, 'matches', {
    get: () => dark,
  })
  return mock
}

describe('resolveTheme', () => {
  const media = makeMatchMedia(true)

  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => media))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns a stored theme when set, else the system theme', () => {
    expect(resolveTheme('light')).toBe('light')
    expect(resolveTheme('dark')).toBe('dark')
    expect(resolveTheme(null)).toBe('dark')
    expect(resolveTheme('system')).toBe('dark')
  })
})

describe('useTheme', () => {
  const media = makeMatchMedia(true)

  beforeEach(() => {
    window.localStorage.clear()
    delete window.document.documentElement.dataset.theme
    vi.stubGlobal('matchMedia', vi.fn(() => media))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults to the system scheme when no override is stored', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.mode).toBe('system')
    expect(result.current.resolved).toBe('dark')
    expect(window.document.documentElement.dataset.theme).toBe('dark')
  })

  it('respects a stored light/dark override', () => {
    window.localStorage.setItem(STORAGE_KEY, 'light')
    const first = renderHook(() => useTheme())
    expect(first.result.current.resolved).toBe('light')
    first.unmount()

    window.localStorage.setItem(STORAGE_KEY, 'dark')
    const second = renderHook(() => useTheme())
    expect(second.result.current.resolved).toBe('dark')
    second.unmount()
  })

  it('toggling persists the choice', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.setTheme('light'))
    expect(result.current.mode).toBe('light')
    expect(result.current.resolved).toBe('light')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('light')
    expect(window.document.documentElement.dataset.theme).toBe('light')
    act(() => result.current.setTheme('dark'))
    expect(result.current.resolved).toBe('dark')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark')
  })

  it('clearing the override removes it and re-follows OS changes', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.setTheme('light'))
    act(() => result.current.clearOverride())
    expect(result.current.mode).toBe('system')
    expect(result.current.resolved).toBe('dark')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()

    act(() => media.trigger(false))
    expect(window.document.documentElement.dataset.theme).toBe('light')
    act(() => media.trigger(true))
    expect(window.document.documentElement.dataset.theme).toBe('dark')
  })

  it('does not re-follow OS changes while an override is set', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.setTheme('light'))
    act(() => media.trigger(true))
    expect(window.document.documentElement.dataset.theme).toBe('light')
    act(() => result.current.clearOverride())
    expect(window.document.documentElement.dataset.theme).toBe('dark')
  })
})