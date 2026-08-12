/**
 * Unit tests for the Models page (``ModelsPage.tsx``): rendering one row per
 * agent/model from ``GET /api/models``, plus the failure and empty states.
 * Uses ``renderWithClient`` for the React Query wrapper and stubs
 * ``window.fetch`` per test.
 */
import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithClient } from '../test/utils'
import ModelsPage from './ModelsPage'

function stubModelsFetch(respond: unknown) {
  const mock = vi
    .fn()
    .mockResolvedValue(
      respond instanceof Error
        ? { ok: false, status: 500, json: async () => ({ detail: respond.message }) }
        : { ok: true, status: 200, json: async () => respond },
    )
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ModelsPage', () => {
  it('renders agent/provider/model rows for each model', async () => {
    stubModelsFetch([
      { agent: 'jd_parsing_agent', provider: 'ollama', model: 'qwen2.5:7b-instruct' },
      { agent: 'cover_letter_agent', provider: 'openai', model: 'gpt-4o' },
    ])
    renderWithClient(<ModelsPage />)

    expect(await screen.findByText('jd_parsing_agent')).toBeInTheDocument()
    expect(screen.getByText('qwen2.5:7b-instruct')).toBeInTheDocument()
    expect(screen.getByText('cover_letter_agent')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
  })

  it('shows the failure empty state when fetching models errors', async () => {
    stubModelsFetch(new Error('backend down'))
    renderWithClient(<ModelsPage />)

    expect(
      await screen.findByText('Failed to load models. Is the backend running?'),
    ).toBeInTheDocument()
  })

  it('shows a plain empty state when there are no models', async () => {
    stubModelsFetch([])
    renderWithClient(<ModelsPage />)
    expect(await screen.findByText('No models found')).toBeInTheDocument()
  })
})