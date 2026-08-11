// Cover Letter tab — renders the Agent 7 output (cover_letter).
// Trust boundary: the cover letter is plain text produced by our own
// pipeline (LLM output, not user-supplied HTML).  It is rendered inside a
// <pre> as text — React escapes the string, so no HTML is interpreted.
import { textFromValue } from './coerce'
import { NoData, Section } from './parts'

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
      <Section label="Cover letter" hasContent>
        <pre className="results-pre">{coverLetter}</pre>
      </Section>
    </div>
  )
}

export default CoverLetterTab