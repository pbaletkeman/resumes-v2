import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { vi } from 'vitest'

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  })
}

export function withClient(
  queryClient: QueryClient,
  children: ReactNode,
): ReactElement {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

export function renderWithClient(
  ui: ReactElement,
  queryClient: QueryClient = createTestQueryClient(),
): RenderResult {
  return render(withClient(queryClient, ui))
}

export function stubMatchMedia(dark = false) {
  const listeners = new Set<EventListener>()
  const media = {
    media: '(prefers-color-scheme: dark)',
    get matches() {
      return dark
    },
    addEventListener: (_type: string, listener: EventListener) => {
      listeners.add(listener)
    },
    removeEventListener: (_type: string, listener: EventListener) => {
      listeners.delete(listener)
    },
    setDark(next: boolean) {
      dark = next
      listeners.forEach((listener) => listener(new Event('change')))
    },
  }
  window.matchMedia = vi.fn().mockReturnValue(media)
  return media
}