// Cover Letter tab — renders the Agent 7 output (cover_letter).
// Trust boundary: the cover letter is plain text produced by our own
// pipeline (LLM output, not user-supplied HTML); PreSection renders it
// escaped inside a <pre>.
import { textFromValue } from './coerce'
import { NoData, PreSection } from './parts'

interface CoverLetterTabProps {
  value: unknown
}

function CoverLetterTab({ value }: CoverLetterTabProps) {
  const coverLetter = textFromValue(value, ['cover_letter', 'text'])

  if (coverLetter === null) {
    return <NoData />
  }

  return (
    <div className="results-panel">
      <PreSection label="Cover letter" text={coverLetter} />
    </div>
  )
}

export default CoverLetterTab