import { pickList, pickString, pickMap } from './coerce'
import { BulletSection, KeyValueTable, NoData, TagSection } from './parts'

interface ParsedJDTabProps {
  value: unknown
}

function ParsedJDTab({ value }: ParsedJDTabProps) {
  const record = value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : null
  if (record === null) {
    return <NoData />
  }

  const role = pickString(record, 'role_title')
  const company = pickString(record, 'company_name')
  const seniority = pickString(record, 'seniority_level')

  return (
    <div className="results-panel">
      {(role || company || seniority) && (
        <section className="results-section">
          <h3>Role</h3>
          <div className="results-role">
            {role && <p>{role}</p>}
            {company && <p>{company}</p>}
            {seniority && <p>{seniority}</p>}
          </div>
        </section>
      )}
      <TagSection label="Required skills" items={pickList(record, 'required_skills')} />
      <TagSection label="Preferred skills" items={pickList(record, 'preferred_skills')} />
      <BulletSection label="Responsibilities" items={pickList(record, 'responsibilities')} />
      <TagSection label="Keywords" items={pickList(record, 'keywords')} />
      <TagSection label="Industry terms" items={pickList(record, 'industry_terms')} />
      <KeyValueTable label="Company signals" entries={pickMap(record, 'company_signals')} />
    </div>
  )
}

export default ParsedJDTab