/**
 * Unit tests for the Models page (``ModelsPage.tsx``): rendering one editable
 * row per agent/model from ``GET /api/models``, inline model/provider edits
 * that ``PATCH`` the override and refresh the table, reset-to-defaults via
 * ``DELETE``, plus the failure and empty states.
 *
 * ``ModelsPage`` uses ``useToast`` (throws outside ``ToastProvider``) so each
 * render is wrapped in a ``ToastProvider`` on top of the shared
 * ``renderWithClient`` React Query wrapper. ``window.fetch`` is stubbed per
 * test; the edit flows use a stateful handler so the refetch triggered by the
 * mutation's ``invalidateQueries`` returns the updated rows.
 *
 * PrimeReact controls in a jsdom DataTable need explicit driving: text is
 * typed with ``userEvent``, and the provider Dropdown is opened with
 * ``userEvent`` then its option picked with ``fireEvent`` after the (statically
 * hidden) overlay panel is forced visible.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTestQueryClient, renderWithClient, stubFetch } from '../test/utils'
import type { ModelSummary } from '../api/types'
import ToastProvider from '../toast/ToastProvider'
import ModelsPage from './ModelsPage'

/** Build a ``ModelSummary`` row with the shared default overridden as needed. */
function makeRow(overrides: Partial<ModelSummary> = {}): ModelSummary {
  return {
    agent: 'jd_parsing_agent',
    provider: 'ollama',
    model: 'qwen2.5:7b-instruct',
    default_provider: 'ollama',
    default_model: 'qwen2.5:7b-instruct',
    is_overridden: false,
    ...overrides,
  }
}

/** Render the page under a fresh QueryClient + ToastProvider. */
function renderPage(queryClient: QueryClient = createTestQueryClient()) {
  return renderWithClient(
    <ToastProvider>
      <ModelsPage />
    </ToastProvider>,
    queryClient,
  )
}

/** Get the first table row of the given agent. */
function rowFor(agent: string): HTMLElement {
  return screen.getByText(agent).closest('tr') as HTMLElement
}

/**
 * Open an agent's provider Dropdown and click the given option. PrimeReact
 * renders the overlay panel with ``display: none`` in jsdom (it has no layout
 * to position against), so it is forced visible before the option is picked.
 */
async function pickProvider(user: ReturnType<typeof userEvent.setup>, row: HTMLElement, label: string) {
  await user.click(row.querySelector('.models-provider') as HTMLElement)
  const panel = document.querySelector('.p-dropdown-panel') as HTMLElement
  panel.style.display = 'block'
  fireEvent.click(within(panel).getByRole('option', { name: label }))
}

/** Stub a stateful fetch handler that applies PATCH/DELETE to ``rows``. */
function stubModelApi(rows: ModelSummary[]) {
  const patched: unknown[] = []
  const fetchMock = stubFetch((url, init) => {
    if (init?.method === 'PATCH') {
      const body = JSON.parse(String(init.body))
      patched.push(body)
      const index = rows.findIndex((row) => row.agent === url.split('/').pop())
      rows[index] = { ...rows[index], ...body, is_overridden: true }
      return { ...rows[index] }
    }
    if (init?.method === 'DELETE') {
      const index = rows.findIndex((row) => row.agent === url.split('/').pop())
      rows[index] = makeRow()
      return { ...rows[index] }
    }
    return [...rows]
  })
  return { patched, fetchMock }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ModelsPage', () => {
  it('renders an editable provider/model row for each agent', async () => {
    stubFetch(() => [
      makeRow(),
      makeRow({
        agent: 'cover_letter_agent',
        provider: 'openai',
        model: 'gpt-4o',
        default_provider: 'openai',
        default_model: 'gpt-4o',
      }),
    ])
    renderPage()

    expect(await screen.findByText('jd_parsing_agent')).toBeInTheDocument()
    expect(screen.getByText('cover_letter_agent')).toBeInTheDocument()
    expect(screen.getByDisplayValue('qwen2.5:7b-instruct')).toBeInTheDocument()
    expect(screen.getByDisplayValue('gpt-4o')).toBeInTheDocument()
    expect(screen.getAllByDisplayValue('Ollama').length).toBeGreaterThan(0)
    expect(screen.getAllByDisplayValue('OpenAI').length).toBeGreaterThan(0)
  })

  it('saves an edited model and shows the updated value', async () => {
    const user = userEvent.setup()
    const rows = [makeRow()]
    const { patched, fetchMock } = stubModelApi(rows)
    renderPage()

    await screen.findByText('jd_parsing_agent')
    const row = rowFor('jd_parsing_agent')
    const modelInput = within(row).getByDisplayValue('qwen2.5:7b-instruct')
    await user.clear(modelInput)
    await user.type(modelInput, 'llama3.1')
    await user.click(within(row).getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/models/jd_parsing_agent',
        expect.objectContaining({ method: 'PATCH' }),
      ),
    )
    expect(patched).toContainEqual({ provider: 'ollama', model: 'llama3.1' })
    await waitFor(() =>
      expect(screen.getByDisplayValue('llama3.1')).toBeInTheDocument(),
    )
  })

  it('switches the provider to openai and saves it', async () => {
    const user = userEvent.setup()
    const rows = [makeRow()]
    const { patched, fetchMock } = stubModelApi(rows)
    renderPage()

    await screen.findByText('jd_parsing_agent')
    const row = rowFor('jd_parsing_agent')
    await pickProvider(user, row, 'OpenAI')
    await user.click(within(row).getByRole('button', { name: /save/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/models/jd_parsing_agent',
        expect.objectContaining({ method: 'PATCH' }),
      ),
    )
    expect(patched).toContainEqual({
      provider: 'openai',
      model: 'qwen2.5:7b-instruct',
    })
  })

  it('disables reset until the agent has a persisted override', async () => {
    stubFetch(() => [makeRow()])
    renderPage()

    await screen.findByText('jd_parsing_agent')
    const row = rowFor('jd_parsing_agent')
    expect(within(row).getByRole('button', { name: /reset/i })).toBeDisabled()
  })

  it('resets an overridden agent back to the defaults', async () => {
    const user = userEvent.setup()
    const rows = [makeRow({ model: 'gpt-4o', is_overridden: true })]
    const { fetchMock } = stubModelApi(rows)
    renderPage()

    await screen.findByText('jd_parsing_agent')
    const row = rowFor('jd_parsing_agent')
    const resetButton = within(row).getByRole('button', { name: /reset/i })
    expect(resetButton).not.toBeDisabled()
    await user.click(resetButton)

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/models/jd_parsing_agent',
        expect.objectContaining({ method: 'DELETE' }),
      ),
    )
    await waitFor(() =>
      expect(screen.getByDisplayValue('qwen2.5:7b-instruct')).toBeInTheDocument(),
    )
  })

  it('shows the failure empty state when fetching models errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'backend down' }),
      }),
    )
    renderPage()

    expect(
      await screen.findByText('Failed to load models. Is the backend running?'),
    ).toBeInTheDocument()
  })

  it('shows a plain empty state when there are no models', async () => {
    stubFetch(() => [])
    renderPage()
    expect(await screen.findByText('No models found')).toBeInTheDocument()
  })
})