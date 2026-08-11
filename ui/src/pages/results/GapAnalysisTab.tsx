// Gap Analysis tab — renders the Agent 3 output (tailoring_strategy).
import { asRecord, pickList, pickText } from './coerce'
import { NoData, TagSection } from './parts'

interface GapAnalysisTabProps {
  value: unknown
}

function GapAnalysisTab({ value }: GapAnalysisTabProps) {
  const record = asRecord(value)
  if (record === null) {
    return <NoData />
  }

  const toneGuidance = pickText(record, 'tone_guidance')

  return (
    <div className="results-panel">
      <TagSection label="Missing skills" items={pickList(record, 'missing_skills')} emptyText="No data" />
      <TagSection label="Weak skills" items={pickList(record, 'weak_skills')} emptyText="No data" />
      <TagSection label="Strong matches" items={pickList(record, 'strong_matches')} emptyText="No data" />
      <TagSection label="Recommended emphasis" items={pickList(record, 'recommended_emphasis')} emptyText="No data" />
      <TagSection label="Keyword strategy" items={pickList(record, 'keyword_strategy')} emptyText="No data" />
      <TagSection label="Bullet plan" items={pickList(record, 'bullet_point_improvement_plan')} emptyText="No data" />
      {toneGuidance !== null && <p className="results-text">{toneGuidance}</p>}
    </div>
  )
}

export default GapAnalysisTab