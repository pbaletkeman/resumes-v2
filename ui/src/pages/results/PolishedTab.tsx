// Polished tab — renders the Agent 6 output (polished_resume).
// Trust boundary: the polished resume is plain text produced by our own
// pipeline (LLM output, not user-supplied HTML).  It is rendered inside a
// <pre> as text — React escapes the string, so no HTML is interpreted.
import { textFromValue } from './coerce'
import { NoData, Section } from './parts'

interface PolishedTabProps {
  value: unknown
}

function PolishedTab({ value }: PolishedTabProps) {
  const polishedResume = textFromValue(value, ['polished_resume', 'text'])

  if (polishedResume === null) {
    return <NoData />
  }

  return (
    <div className="results-panel">
      <Section label="Polished resume" hasContent>
        <pre className="results-pre">{polishedResume}</pre>
      </Section>
    </div>
  )
}

export default PolishedTab