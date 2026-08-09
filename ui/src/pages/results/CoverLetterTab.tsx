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