import { TabPanel, TabView } from 'primereact/tabview'
import ATSTab from './ATSTab'
import CoverLetterTab from './CoverLetterTab'
import GapAnalysisTab from './GapAnalysisTab'
import ParsedJDTab from './ParsedJDTab'
import ParsedResumeTab from './ParsedResumeTab'
import PolishedTab from './PolishedTab'
import RewrittenResumeTab from './RewrittenResumeTab'

type ResultKey =
  | 'parsed_job_description'
  | 'parsed_resume'
  | 'tailoring_strategy'
  | 'rewritten_resume'
  | 'ats_optimized_resume'
  | 'polished_resume'
  | 'cover_letter'

const TAB_KEYS: ResultKey[] = [
  'parsed_job_description',
  'parsed_resume',
  'tailoring_strategy',
  'rewritten_resume',
  'ats_optimized_resume',
  'polished_resume',
  'cover_letter',
]

const TAB_HEADERS: Record<ResultKey, string> = {
  parsed_job_description: 'Parsed JD',
  parsed_resume: 'Parsed Resume',
  tailoring_strategy: 'Gap Analysis',
  rewritten_resume: 'Rewritten Resume',
  ats_optimized_resume: 'ATS',
  polished_resume: 'Polished',
  cover_letter: 'Cover Letter',
}

interface ResultsTabViewProps {
  result?: Record<string, unknown> | null
}

function renderTabBody(key: ResultKey, value: unknown) {
  switch (key) {
    case 'parsed_job_description':
      return <ParsedJDTab value={value} />
    case 'parsed_resume':
      return <ParsedResumeTab value={value} />
    case 'tailoring_strategy':
      return <GapAnalysisTab value={value} />
    case 'rewritten_resume':
      return <RewrittenResumeTab value={value} />
    case 'ats_optimized_resume':
      return <ATSTab value={value} />
    case 'polished_resume':
      return <PolishedTab value={value} />
    case 'cover_letter':
      return <CoverLetterTab value={value} />
  }
}

function ResultsTabView({ result }: ResultsTabViewProps) {
  if (result === null || result === undefined) {
    return null
  }

  return (
    <section className="run-results">
      <h2>Results</h2>
      <TabView>
        {TAB_KEYS.map((key) => (
          <TabPanel key={key} header={TAB_HEADERS[key]}>
            <div className="results-panel">{renderTabBody(key, result[key])}</div>
          </TabPanel>
        ))}
      </TabView>
    </section>
  )
}

export default ResultsTabView