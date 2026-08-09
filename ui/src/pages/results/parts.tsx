import type { ReactNode } from 'react'
import { Tag } from 'primereact/tag'
import { pickList, pickString } from './coerce'

export function NoData({ label = 'No data' }: { label?: string }) {
  return <p className="results-no-data">{label}</p>
}

export function Section({
  label,
  hasContent,
  children,
}: {
  label: string
  hasContent: boolean
  children: ReactNode
}) {
  return (
    <section className="results-section">
      <h3>{label}</h3>
      {hasContent ? children : <NoData />}
    </section>
  )
}

export function ExperienceEntryView({ entry }: { entry: Record<string, unknown> }) {
  const title = pickString(entry, 'title')
  const company = pickString(entry, 'company')
  const dates = pickString(entry, 'dates')
  const responsibilities = pickList(entry, 'responsibilities')
  const achievements = pickList(entry, 'achievements')
  const metrics = pickList(entry, 'metrics')
  const hasBody =
    responsibilities.length > 0 || achievements.length > 0 || metrics.length > 0

  return (
    <div className="results-experience">
      <div className="results-experience-head">
        <span className="results-experience-title">{title ?? 'Untitled role'}</span>
        {company && <span className="results-experience-company">{company}</span>}
        {dates && <span className="results-experience-dates">{dates}</span>}
      </div>
      {hasBody && (
        <div className="results-experience-body">
          {responsibilities.length > 0 && (
            <BulletSection label="Responsibilities" items={responsibilities} />
          )}
          {achievements.length > 0 && (
            <BulletSection label="Achievements" items={achievements} />
          )}
          {metrics.length > 0 && <BulletSection label="Metrics" items={metrics} />}
        </div>
      )}
    </div>
  )
}

interface SectionProps {
  label: string
  items: string[]
  emptyText?: string
}

export function TagSection({ label, items, emptyText }: SectionProps) {
  if (items.length === 0) {
    return emptyText === undefined ? null : (
      <section className="results-section">
        <h3>{label}</h3>
        <NoData label={emptyText} />
      </section>
    )
  }
  return (
    <section className="results-section">
      <h3>{label}</h3>
      <div className="results-tags">
        {items.map((item) => (
          <Tag key={item} value={item} />
        ))}
      </div>
    </section>
  )
}

export function BulletSection({ label, items, emptyText }: SectionProps) {
  if (items.length === 0) {
    return emptyText === undefined ? null : (
      <section className="results-section">
        <h3>{label}</h3>
        <NoData label={emptyText} />
      </section>
    )
  }
  return (
    <section className="results-section">
      <h3>{label}</h3>
      <ul className="results-bullets">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

interface TableProps {
  label: string
  entries: Record<string, string>
  emptyText?: string
}

export function KeyValueTable({ label, entries, emptyText }: TableProps) {
  const keys = Object.keys(entries)
  if (keys.length === 0) {
    return emptyText === undefined ? null : (
      <section className="results-section">
        <h3>{label}</h3>
        <NoData label={emptyText} />
      </section>
    )
  }
  return (
    <section className="results-section">
      <h3>{label}</h3>
      <table className="results-table">
        <tbody>
          {keys.map((key) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{entries[key]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}