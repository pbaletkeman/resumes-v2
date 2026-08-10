import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PagedFile } from '../api/types'
import { renderWithClient } from '../test/utils'

const toast = vi.hoisted(() => ({ show: vi.fn(), clear: vi.fn() }))

vi.mock('../toast/ToastContext', () => ({
  useToast: () => toast,
}))

import FilesPage from './FilesPage'

const INPUT: PagedFile = {
  items: [
    {
      name: '20260809_smith_resume.md',
      size: 2048,
      modified: '2026-08-09T14:17:00Z',
      type: 'md',
      path: 'output/20260809_smith_resume.md',
    },
    {
      name: '20260809_smith_cover.txt',
      size: 512,
      modified: '2026-08-09T14:17:00Z',
      type: 'txt',
      path: 'output/20260809_smith_cover.txt',
    },
  ],
  page: 1,
  page_size: 20,
  total: 2,
  total_pages: 1,
}

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
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

afterEach(() => {
  vi.unstubAllGlobals()
  toast.show.mockClear()
  toast.clear.mockClear()
})

describe('FilesPage', () => {
  it('renders file rows from a PagedFile', async () => {
    stubFetch(() => INPUT)
    renderWithClient(<FilesPage />)

    expect(
      await screen.findByText('20260809_smith_resume.md'),
    ).toBeInTheDocument()
    expect(screen.getByText('20260809_smith_cover.txt')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
  })

  it('fires the delete mutation with selected paths and surfaces the result', async () => {
    const fetchMock = stubFetch((url, init) => {
      if (url.startsWith('/api/files/generated')) {
        return INPUT
      }
      if (url === '/api/files' && init?.method === 'DELETE') {
        return { deleted: ['output/20260809_smith_resume.md'], missing: [] }
      }
      return { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
    })
    renderWithClient(<FilesPage />)

    const row = await screen.findByText('20260809_smith_resume.md')
    const checkbox = row
      .closest('tr')
      ?.querySelector('.p-checkbox-input') as HTMLInputElement
    expect(checkbox).not.toBeUndefined()
    fireEvent.click(checkbox)

    fireEvent.click(screen.getByRole('button', { name: /delete selected \(1\)/i }))

    expect(await screen.findByText('Confirm deletion')).toBeInTheDocument()
    const dialog = document.querySelector('.p-confirm-dialog')
    const acceptButton = dialog?.querySelector('.p-confirm-dialog-accept')
    if (acceptButton === null || acceptButton === undefined) {
      throw new Error('accept button not found')
    }
    fireEvent.click(acceptButton)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/files', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: ['output/20260809_smith_resume.md'] }),
    }))
    await waitFor(() =>
      expect(toast.show).toHaveBeenCalledWith(
        expect.objectContaining({ summary: 'Deleted' }),
      ),
    )
  })
})