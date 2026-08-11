/**
 * Shared renderers for the results tabs.
 *
 * The tab components read their (already coerced) data and describe it
 * declaratively with these parts: a `Section` wrapper with a heading, tag /
 * bullet / key-value content blocks, `ExperienceSection` for work history,
 * `ParagraphSection` / `PreSection` for single blocks of text, and a
 * `NoData` placeholder.  Every list-style renderer accepts an `emptyText`;
 * when set it renders the placeholder, otherwise it renders nothing (so tabs
 * can silently skip empty sections).
 */
import type { ReactNode } from 'react'
import { Tag } from 'primereact/tag'
import { pickList, pickString } from './coerce'

/** A small centered placeholder shown when a section has no content. */
export function NoData({ label = 'No data' }: { label?: string }) {
  return <p className="results-no-data">{label}</p>
}

/**
 * A titled section.  Renders `children` when `hasContent` is true, otherwise
 * a `NoData` placeholder.
 */
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

/**
 * A titled section rendering a single paragraph of text.  Renders `NoData`
 * when `text` is null (e.g. the Summary and Contact blocks on the parsed /
 * rewritten resume tabs).
 */
export function ParagraphSection({
  label,
  text,
}: {
  label: string
  text: string | null
}) {
  return (
    <Section label={label} hasContent={text !== null}>
      <p>{text}</p>
    </Section>
  )
}

/**
 * A titled section rendering pre-formatted text in a `<pre>` block.  Renders
 * `NoData` when `text` is null (e.g. the polished resume, cover letter, and
 * ATS final resume).
 */
export function PreSection({ label, text }: { label: string; text: string | null }) {
  return (
    <Section label={label} hasContent={text !== null}>
      {text !== null && <pre className="results-pre">{text}</pre>}
    </Section>
  )
}

/**
 * One work-history row.  Reads `title` / `company` / `dates` and the
 * `responsibilities` / `achievements` / `metrics` lists off a loose entry
 * dict, renders the header line, and each non-empty list as a
 * `BulletSection`.
 */
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

/**
 * A titled "Experience" section rendering each work-history entry via
 * `ExperienceEntryView`.  Renders `NoData` when there are no entries.
 */
export function ExperienceSection({
  entries,
}: {
  entries: Record<string, unknown>[]
}) {
  return (
    <Section label="Experience" hasContent={entries.length > 0}>
      <div className="results-experiences">
        {entries.map((entry, index) => (
          <ExperienceEntryView key={index} entry={entry} />
        ))}
      </div>
    </Section>
  )
}

interface SectionProps {
  label: string
  items: string[]
  emptyText?: string
}

/**
 * A titled section rendering `items` as PrimeReact `Tag`s.  With `emptyText`
 * set, renders a `NoData` placeholder when there are no items; otherwise
 * renders nothing.
 */
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

/**
 * A titled section rendering `items` as a bulleted list.  With `emptyText`
 * set, renders a `NoData` placeholder when there are no items; otherwise
 * renders nothing.
 */
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

/**
 * A titled section rendering `entries` as a two-column key/value table.
 * With `emptyText` set, renders a `NoData` placeholder when there are no
 * entries; otherwise renders nothing.
 */
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