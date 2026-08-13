/**
 * Unit tests for the Run page (``RunPage.tsx``): the form flow (pasted text
 * wins over an uploaded file, empty-input warn toast, disabled-while-active
 * button) plus focused tests for the status helpers extracted in Phase 15
 * (``isTaskActive`` and ``taskStatusLabel``) and the page-flow header.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TaskStatus } from '../api/types'

const hooks = vi.hoisted(() => ({
  invoke: { isPending: false, mutate: vi.fn() },
  task: { data: null as TaskStatus | null },
}))

vi.mock('../api/hooks', () => ({
  useInvokePipeline: () => hooks.invoke,
  usePollTask: () => hooks.task,
}))

const toast = vi.hoisted(() => ({ show: vi.fn(), clear: vi.fn() }))

vi.mock('../toast/ToastContext', () => ({
  useToast: () => toast,
}))

vi.mock('primereact/fileupload', async () => {
  const { forwardRef } = await import('react')
  const mockedFile = new File(['job'], 'jd.txt', { type: 'text/plain' })
  const MockFileUpload = forwardRef<
    unknown,
    { onSelect: (e: { files: File[] }) => void }
  >(function MockFileUpload({ onSelect }, _ref) {
    return (
      <button
        type="button"
        className="file-upload-stub"
        onClick={() => onSelect({ files: [mockedFile] })}
      >
        Upload file
      </button>
    )
  })
  return { FileUpload: MockFileUpload }
})

import RunPage from './RunPage'
import { isTaskActive, taskStatusLabel } from './runStatus'

const JOB_TEXT = 'Company needs a senior frontend engineer. React, TypeScript.'
const RESUME_TEXT = 'React developer with three years of TypeScript experience.'

beforeEach(() => {
  hooks.invoke = { isPending: false, mutate: vi.fn() }
  hooks.task = { data: null }
  toast.show.mockClear()
  toast.clear.mockClear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function typeText(id: string, value: string) {
  fireEvent.change(screen.getByLabelText(id), { target: { value } })
}

describe('RunPage form', () => {
  it('submits pasted text and wins over an uploaded file', () => {
    render(<RunPage />)
    typeText('Job Description', JOB_TEXT)
    typeText('Resume', RESUME_TEXT)
    fireEvent.click(screen.getAllByRole('button', { name: 'Upload file' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Upload file' })[0])

    fireEvent.click(screen.getByRole('button', { name: 'Run Pipeline' }))

    expect(hooks.invoke.mutate).toHaveBeenCalledTimes(1)
    const formData = hooks.invoke.mutate.mock.calls[0][0] as FormData
    expect(formData.get('job_description')).toBe(JOB_TEXT)
    expect(formData.get('resume')).toBe(RESUME_TEXT)
    expect(formData.get('job_file')).toBeNull()
    expect(formData.get('resume_file')).toBeNull()
  })

  it('disables the Run Pipeline button while a run is active', () => {
    hooks.invoke.isPending = true
    render(<RunPage />)
    expect(screen.getByRole('button', { name: 'Starting...' })).toBeDisabled()
  })

  it('shows a warning toast when both inputs are empty', () => {
    render(<RunPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Pipeline' }))
    expect(hooks.invoke.mutate).not.toHaveBeenCalled()
    expect(toast.show).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'warn',
        detail: expect.stringMatching(/job description/i),
      }),
    )
  })

  it('submits the default modern resume template', () => {
    render(<RunPage />)
    typeText('Job Description', JOB_TEXT)
    typeText('Resume', RESUME_TEXT)

    fireEvent.click(screen.getByRole('button', { name: 'Run Pipeline' }))

    expect(hooks.invoke.mutate).toHaveBeenCalledTimes(1)
    const formData = hooks.invoke.mutate.mock.calls[0][0] as FormData
    expect(formData.get('resume_template')).toBe('modern')
  })

  it('sends the selected resume template', async () => {
    const user = userEvent.setup()
    render(<RunPage />)
    typeText('Job Description', JOB_TEXT)
    typeText('Resume', RESUME_TEXT)

    // PrimeReact renders the Dropdown overlay panel with `display: none` in
    // jsdom (it has no layout to position against), so force it visible before
    // picking the option.
    await user.click(document.querySelector('.run-template-dropdown') as HTMLElement)
    const panel = document.querySelector('.p-dropdown-panel') as HTMLElement
    panel.style.display = 'block'
    fireEvent.click(within(panel).getByRole('option', { name: 'All three' }))

    fireEvent.click(screen.getByRole('button', { name: 'Run Pipeline' }))

    expect(hooks.invoke.mutate).toHaveBeenCalledTimes(1)
    const formData = hooks.invoke.mutate.mock.calls[0][0] as FormData
    expect(formData.get('resume_template')).toBe('all')
  })
})

describe('isTaskActive', () => {
  it('is true while a task has not reached a terminal state', () => {
    expect(isTaskActive(undefined)).toBe(true)
    expect(isTaskActive('pending')).toBe(true)
    expect(isTaskActive('running')).toBe(true)
  })

  it('is false once a task has settled', () => {
    expect(isTaskActive('completed')).toBe(false)
    expect(isTaskActive('failed')).toBe(false)
  })
})

describe('taskStatusLabel', () => {
  it('renders a human-readable label per status', () => {
    expect(taskStatusLabel(undefined)).toBe('Pending')
    expect(taskStatusLabel('pending')).toBe('Pending')
    expect(taskStatusLabel('running')).toBe('Running')
    expect(taskStatusLabel('completed')).toBe('Completed')
    expect(taskStatusLabel('failed')).toBe('Failed')
  })
})