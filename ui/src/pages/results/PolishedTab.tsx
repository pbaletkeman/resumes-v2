// Polished tab — renders the Agent 6 output (polished_resume).
// Trust boundary: the polished resume is plain text produced by our own
// pipeline (LLM output, not user-supplied HTML); PreSection renders it
// escaped inside a <pre>.
import { textFromValue } from './coerce'
import { NoData, PreSection } from './parts'

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
      <PreSection label="Polished resume" text={polishedResume} />
    </div>
  )
}

export default PolishedTab