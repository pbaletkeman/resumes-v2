/**
 * Unit tests for the color-scheme toggle (``theme/ThemeToggle.tsx``): the
 * three mode options render, selecting one persists it to the ``theme``
 * localStorage key and applies the ``data-theme`` attribute, and selecting
 * System removes the stored override.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { stubMatchMedia } from '../test/utils'
import ThemeToggle from './ThemeToggle'

describe('ThemeToggle', () => {
  beforeEach(() => {
    window.localStorage.clear()
    delete window.document.documentElement.dataset.theme
    stubMatchMedia(false)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the three mode options', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'System' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Light' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dark' })).toBeInTheDocument()
  })

  it('selecting a mode calls the theme hook setter and applies it', () => {
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(window.localStorage.getItem('theme')).toBe('dark')
    expect(window.document.documentElement.dataset.theme).toBe('dark')
  })

  it('selecting the system mode removes the stored override', () => {
    window.localStorage.setItem('theme', 'dark')
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole('button', { name: 'System' }))
    expect(window.localStorage.getItem('theme')).toBe('system')
    expect(window.document.documentElement.dataset.theme).toBe('light')
  })
})