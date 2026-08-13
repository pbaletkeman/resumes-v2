/**
 * Unit tests for the React Query hooks (``hooks.ts``): ``useModels`` fetches
 * the model summary, ``useFiles`` passes params through and keeps previous
 * data while refetching, and ``useDeleteFiles`` invalidates the file queries
 * on success. Renders hooks under a fresh test ``QueryClient`` and drives
 * ``window.fetch`` via the shared ``stubFetch``.
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useDeleteFiles,
  useFiles,
  useModels,
  useResetAgentModel,
  useUpdateAgentModel,
} from './hooks'
import { createTestQueryClient, stubFetch, withClient } from '../test/utils'
import type { PagedFile } from './types'

function makePaged(items: PagedFile['items'], page: number): PagedFile {
  return {
    items,
    page,
    page_size: 20,
    total: items.length,
    total_pages: 1,
  }
}

describe('useModels', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [{ agent: 'jd_parsing_agent', provider: 'ollama', model: 'qwen' }],
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders models on success', async () => {
    const queryClient = createTestQueryClient()
    const wrapper = ({ children }: { children?: ReactNode }) =>
      withClient(queryClient, children)

    const { result } = renderHook(() => useModels(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([
      { agent: 'jd_parsing_agent', provider: 'ollama', model: 'qwen' },
    ])
    expect(fetchMock).toHaveBeenCalledWith('/api/models', undefined)
  })
})

describe('useFiles', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('passes params through and keeps previous data while refetching', async () => {
    const calls: string[] = []
    stubFetch((url) => {
      calls.push(url)
      if (url.includes('page=3')) {
        return makePaged(
          [{ name: 'b.md', size: 3, modified: '', type: 'md', path: 'output/b.md' }],
          3,
        )
      }
      return makePaged(
        [{ name: 'a.md', size: 1, modified: '', type: 'md', path: 'output/a.md' }],
        2,
      )
    })

    const queryClient = createTestQueryClient()
    const wrapper = ({ children }: { children?: ReactNode }) =>
      withClient(queryClient, children)

    const { result, rerender } = renderHook(
      (page: number) => useFiles('generated', { page }),
      {
        initialProps: 2,
        wrapper,
      },
    )
    await waitFor(() =>
      expect(result.current.data?.items).toEqual([
        { name: 'a.md', size: 1, modified: '', type: 'md', path: 'output/a.md' },
      ]),
    )
    expect(calls).toEqual(['/api/files/generated?page=2'])

    const previous = result.current.data
    rerender(3)

    expect(result.current.data).toBe(previous)
    expect(result.current.isPlaceholderData).toBe(true)

    await waitFor(() =>
      expect(result.current.data?.items).toEqual([
        { name: 'b.md', size: 3, modified: '', type: 'md', path: 'output/b.md' },
      ]),
    )
    expect(calls).toContain('/api/files/generated?page=3')
  })
})

describe('useDeleteFiles', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('invalidates files queries on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ deleted: ['output/a.md'], missing: [] }),
      } as unknown as Response),
    )

    const queryClient = createTestQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = ({ children }: { children?: ReactNode }) =>
      withClient(queryClient, children)

    const { result } = renderHook(() => useDeleteFiles(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync(['output/a.md'])
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['files'] })
    expect(queryClient.getQueryCache().findAll({ queryKey: ['files'] }).length).toBe(0)
  })
})

describe('useUpdateAgentModel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('PATCHes the override and invalidates models queries on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          agent: 'jd_parsing_agent',
          provider: 'ollama',
          model: 'llama3.1',
          default_provider: 'ollama',
          default_model: 'qwen',
          is_overridden: true,
        }),
      } as unknown as Response),
    )

    const queryClient = createTestQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = ({ children }: { children?: ReactNode }) =>
      withClient(queryClient, children)

    const { result } = renderHook(() => useUpdateAgentModel(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({
        agent: 'jd_parsing_agent',
        provider: 'ollama',
        model: 'llama3.1',
      })
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['models'] })
  })
})

describe('useResetAgentModel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('DELETEs the override and invalidates models queries on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          agent: 'jd_parsing_agent',
          provider: 'ollama',
          model: 'qwen',
          default_provider: 'ollama',
          default_model: 'qwen',
          is_overridden: false,
        }),
      } as unknown as Response),
    )

    const queryClient = createTestQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = ({ children }: { children?: ReactNode }) =>
      withClient(queryClient, children)

    const { result } = renderHook(() => useResetAgentModel(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync('jd_parsing_agent')
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['models'] })
  })
})