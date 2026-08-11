// ATS tab — renders the Agent 5 output (ats_optimized_resume).
import { Tag } from 'primereact/tag'
import { asRecord, pickList, pickNumber, pickText } from './coerce'
import { BulletSection, NoData, PreSection, Section, TagSection } from './parts'

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
  const record = asRecord(value)
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
      {/* Trust boundary: `final_resume` is plain text from our own pipeline
          (LLM output, not user-supplied HTML); PreSection renders it escaped. */}
      <PreSection label="Final resume" text={finalResume} />
    </div>
  )
}

export default ATSTab