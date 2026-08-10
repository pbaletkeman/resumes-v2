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
          unknown_key: 'output/something.txt',
        }}
      />,
    )
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(3)
    expect(links[0]).toHaveAttribute(
      'href',
      '/api/outputs/20260809_smith_resume.txt',
    )
    expect(screen.getByText('Resume (txt)')).toBeInTheDocument()
    expect(screen.getByText('Resume (md)')).toBeInTheDocument()
    expect(screen.getByText('Cover letter (md)')).toBeInTheDocument()
    expect(screen.queryByText('Resume (docx)')).not.toBeInTheDocument()
  })

  it('renders nothing when no known keys exist', () => {
    const { container } = render(<DownloadsRow outputFiles={{ other: 'output/a.md' }} />)
    expect(container.querySelector('a')).toBeNull()
  })
})