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