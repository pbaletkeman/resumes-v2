/**
 * Unit tests for the downloads row (``results/DownloadsRow.tsx``): renders one
 * link per known ``output_files`` key on ``/api/outputs/...`` URLs, and
 * nothing when there are no known keys.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import DownloadsRow from './DownloadsRow'

describe('DownloadsRow', () => {
  it('renders nothing when outputFiles is null or undefined', () => {
    const { container } = render(<DownloadsRow outputFiles={null} />)
    expect(container.textContent).toBe('')
    expect(container.querySelector('a')).toBeNull()
  })

  it('renders one link per known output_files entry', () => {
    render(
      <DownloadsRow
        outputFiles={{
          resume_plaintext: 'output/20260809_smith_resume.txt',
          resume_markdown: 'output/20260809_smith_resume.md',
          cover_letter_markdown: 'output/20260809_smith_cover.md',
          cover_letter_docx: 'output/20260809_smith_cover.docx',
          cover_letter_pdf: 'output/20260809_smith_cover.pdf',
          unknown_key: 'output/something.txt',
        }}
      />,
    )
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(5)
    expect(links[0]).toHaveAttribute(
      'href',
      '/api/outputs/20260809_smith_resume.txt',
    )
    expect(screen.getByText('Resume (txt)')).toBeInTheDocument()
    expect(screen.getByText('Resume (md)')).toBeInTheDocument()
    expect(screen.getByText('Cover letter (md)')).toBeInTheDocument()
    expect(screen.getByText('Cover letter (docx)')).toBeInTheDocument()
    expect(screen.getByText('Cover letter (pdf)')).toBeInTheDocument()
    expect(screen.queryByText('Resume (docx)')).not.toBeInTheDocument()
  })

  it('renders nothing when no known keys exist', () => {
    const { container } = render(<DownloadsRow outputFiles={{ other: 'output/a.md' }} />)
    expect(container.querySelector('a')).toBeNull()
  })

  it('renders namespaced links when every resume layout is generated', () => {
    render(
      <DownloadsRow
        outputFiles={{
          resume_modern_markdown: 'output/20260809_smith_resume-modern.md',
          resume_classic_markdown: 'output/20260809_smith_resume-classic.md',
          resume_minimal_markdown: 'output/20260809_smith_resume-minimal.md',
          resume_modern_pdf: 'output/20260809_smith_resume-modern.pdf',
          resume_classic_pdf: 'output/20260809_smith_resume-classic.pdf',
          resume_minimal_pdf: 'output/20260809_smith_resume-minimal.pdf',
        }}
      />,
    )
    expect(screen.getByText('Resume Modern (md)')).toBeInTheDocument()
    expect(screen.getByText('Resume Classic (md)')).toBeInTheDocument()
    expect(screen.getByText('Resume Minimal (md)')).toBeInTheDocument()
    expect(screen.getByText('Resume Modern (pdf)')).toBeInTheDocument()
    expect(screen.getByText('Resume Classic (pdf)')).toBeInTheDocument()
    expect(screen.getByText('Resume Minimal (pdf)')).toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(6)
  })
})