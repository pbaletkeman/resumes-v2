// Parsed Resume tab — renders the Agent 2 output (parsed_resume).
import { asRecord, pickList, pickObjectList, pickString } from './coerce'
import {
  BulletSection,
  ExperienceSection,
  NoData,
  ParagraphSection,
  TagSection,
} from './parts'

interface ParsedResumeTabProps {
  value: unknown
}

function ParsedResumeTab({ value }: ParsedResumeTabProps) {
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
  const name = pickString(record, 'name')
  const phone = pickString(record, 'phone')
  const email = pickString(record, 'email')
  const linkedin = pickString(record, 'linkedin')
  const github = pickString(record, 'github')
  const contact = [name, phone, email, linkedin, github].filter(
    (item): item is string => item !== null,
  )
  const contactText = contact.length > 0 ? contact.join(' · ') : null

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
      <ParagraphSection label="Contact" text={contactText} />
    </div>
  )
}

export default ParsedResumeTab