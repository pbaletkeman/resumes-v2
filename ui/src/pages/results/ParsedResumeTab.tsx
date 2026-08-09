import { pickList, pickObjectList, pickString } from './coerce'
import {
  BulletSection,
  ExperienceEntryView,
  NoData,
  Section,
  TagSection,
} from './parts'

interface ParsedResumeTabProps {
  value: unknown
}

function ParsedResumeTab({ value }: ParsedResumeTabProps) {
  const record =
    value !== null && typeof value === 'object'
      ? (value as Record<string, unknown>)
      : null
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
      <Section label="Summary" hasContent={summary !== null}>
        <p>{summary}</p>
      </Section>
      <TagSection label="Skills" items={skills} emptyText="No data" />
      <Section label="Experience" hasContent={experience.length > 0}>
        <div className="results-experiences">
          {experience.map((entry, index) => (
            <ExperienceEntryView key={index} entry={entry} />
          ))}
        </div>
      </Section>
      <BulletSection label="Projects" items={projects} emptyText="No data" />
      <BulletSection
        label="Certifications"
        items={certifications}
        emptyText="No data"
      />
      <BulletSection label="Education" items={education} emptyText="No data" />
      <Section label="Contact" hasContent={contactText !== null}>
        <p>{contactText}</p>
      </Section>
    </div>
  )
}

export default ParsedResumeTab