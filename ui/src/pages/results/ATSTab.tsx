import { Tag } from 'primereact/tag'
import { pickList, pickNumber, pickText } from './coerce'
import { BulletSection, NoData, Section, TagSection } from './parts'

interface ATSTabProps {
  value: unknown
}

function scoreSeverity(score: number): 'success' | 'warning' | 'danger' {
  if (score < 50) {
    return 'danger'
  }
  if (score < 80) {
    return 'warning'
  }
  return 'success'
}

function ATSTab({ value }: ATSTabProps) {
  const record =
    value !== null && typeof value === 'object'
      ? (value as Record<string, unknown>)
      : null
  if (record === null) {
    return <NoData />
  }

  const score = pickNumber(record, 'ats_score')
  const missingKeywords = pickList(record, 'missing_keywords')
  const formattingIssues = pickList(record, 'formatting_issues')
  const clarityIssues = pickList(record, 'clarity_issues')
  const fixes = pickList(record, 'recommended_fixes')
  const autoFixes = pickList(record, 'auto_fixes_applied')
  const finalResume = pickText(record, 'final_resume')

  return (
    <div className="results-panel">
      <Section label="Score" hasContent={score !== null}>
        {score !== null && <Tag value={score} severity={scoreSeverity(score)} />}
      </Section>
      <TagSection label="Missing keywords" items={missingKeywords} emptyText="No data" />
      <BulletSection label="Formatting issues" items={formattingIssues} emptyText="No data" />
      <BulletSection label="Clarity issues" items={clarityIssues} emptyText="No data" />
      <BulletSection label="Recommended fixes" items={fixes} emptyText="No data" />
      <BulletSection label="Auto-fixes applied" items={autoFixes} emptyText="No data" />
      <Section label="Final resume" hasContent={finalResume !== null}>
        <pre className="results-pre">{finalResume}</pre>
      </Section>
    </div>
  )
}

export default ATSTab