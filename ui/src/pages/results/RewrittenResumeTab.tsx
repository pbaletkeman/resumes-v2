// Rewritten Resume tab — renders the Agent 4 output (rewritten_resume).
import { asRecord, pickList, pickObjectList, pickString } from './coerce'
import {
  BulletSection,
  ExperienceSection,
  NoData,
  ParagraphSection,
  TagSection,
} from './parts'

interface RewrittenResumeTabProps {
  value: unknown
}

function RewrittenResumeTab({ value }: RewrittenResumeTabProps) {
  const record = asRecord(value)
  if (record === null) {
    return <NoData />
  }

  const summary = pickString(record, 'summary')
  const skills = pickList(record, 'skills')
  const experience = pickObjectList(record, 'experience')
  const projects = pickList(record, 'projects')
  const certifications = pickList(record, 'certifications')
  const education = pickList(record, 'education')

  return (
    <div className="results-panel">
      <ParagraphSection label="Summary" text={summary} />
      <TagSection label="Skills" items={skills} emptyText="No data" />
      <ExperienceSection entries={experience} />
      <BulletSection label="Projects" items={projects} emptyText="No data" />
      <BulletSection
        label="Certifications"
        items={certifications}
        emptyText="No data"
      />
      <BulletSection label="Education" items={education} emptyText="No data" />
    </div>
  )
}

export default RewrittenResumeTab