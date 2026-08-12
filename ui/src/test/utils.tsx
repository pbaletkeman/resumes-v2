/**
 * Shared test helpers for rendering components under React Query.
 *
 * ``renderWithClient`` / ``withClient`` wrap a component in a fresh
 * QueryClientProvider whose queries have retries disabled and the cache kept
 * alive (``gcTime: Infinity``), so tests get deterministic, single-shot query
 * behavior. Tests that additionally need routing or toasts layer their own
 * wrappers on top (e.g. RunPage.test.tsx). ``stubMatchMedia`` replaces
 * ``window.matchMedia`` with a controllable stub used by the theme tests to
 * simulate OS light/dark changes. ``stubFetch`` installs a handler-driven
 * ``window.fetch`` mock shared by the API and page tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { vi } from 'vitest'

/**
 * Build a QueryClient tuned for tests: no retries and an infinite cache so
 * queries never keep retrying or get garbage-collected mid-test.
 */
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

/** Wrap children in a ``QueryClientProvider`` using the given client. */
export function withClient(
  queryClient: QueryClient,
  children: ReactNode,
): ReactElement {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

/**
 * Render a component inside a fresh QueryClientProvider (defaults to
 * ``createTestQueryClient`` unless one is passed).
 */
export function renderWithClient(
  ui: ReactElement,
  queryClient: QueryClient = createTestQueryClient(),
): RenderResult {
  return render(withClient(queryClient, ui))
}

/**
 * Stub ``window.matchMedia`` for jsdom with a controllable media object.
 *
 * Starts in the ``matches`` state given by ``dark`` and fires registered
 * ``change`` listeners when ``setDark`` is called, letting theme tests simulate
 * an OS color-scheme flip.
 */
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

/**
 * Stub ``window.fetch`` with a handler-driven mock.
 *
 * Every call resolves with ``ok: true`` / ``status 200`` and produces its JSON
 * body by invoking ``handler(url, init)``, so a test can return different
 * payloads per URL in one stub. Returns the mock so tests can assert on the
 * exact calls made.
 */
export function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(
    (url: string, init?: RequestInit) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => handler(url, init),
      }) as unknown as Response,
  )
  vi.stubGlobal('fetch', mock)
  return mock
}