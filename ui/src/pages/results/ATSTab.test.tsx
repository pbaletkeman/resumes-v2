import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ATSTab from './ATSTab'

function scoreTagClass(score: number): string {
  render(<ATSTab value={{ ats_score: score, final_resume: 'RESUME' }} />)
  const value = screen.getByText(String(score))
  const tag = value.closest('.p-tag')
  return tag?.className ?? ''
}

describe('ATSTab score severity', () => {
  it('maps a score below 50 to danger (red)', () => {
    expect(scoreTagClass(40)).toContain('p-tag-danger')
  })

  it('maps a score in [50, 80) to warning (orange)', () => {
    expect(scoreTagClass(65)).toContain('p-tag-warning')
  })

  it('maps a score of 80+ to success (green)', () => {
    expect(scoreTagClass(95)).toContain('p-tag-success')
  })

  it('does not render a score tag when ats_score is missing', () => {
    const { container } = render(<ATSTab value={{ final_resume: 'RESUME' }} />)
    const scoreSection = container.querySelector('.results-section')
    expect(scoreSection?.querySelector('.p-tag')).not.toBeInTheDocument()
  })
})