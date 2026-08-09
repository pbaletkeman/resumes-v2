export interface ModelSummary {
  agent: string
  provider: string
  model: string
}

export type TaskStatusName = 'pending' | 'running' | 'completed' | 'failed'

export interface TaskCreated {
  task_id: string
}

export interface TaskStatus {
  status: TaskStatusName
  result?: Record<string, unknown> | null
  error?: string | null
  created_at?: number | null
  completed_at?: number | null
}

export interface FileMeta {
  name: string
  size: number
  modified: string
  type: string
  path: string
}

export interface PagedFile {
  items: FileMeta[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface DeleteFilesResponse {
  deleted: string[]
  missing: string[]
}

export interface ExperienceEntry {
  title?: string
  company?: string
  dates?: string
  responsibilities?: string[]
  achievements?: string[]
  metrics?: string[]
}

export interface JDParsingOutput {
  role_title: string
  company_name: string
  seniority_level: string
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  keywords: string[]
  industry_terms: string[]
  company_signals: Record<string, string>
}

export interface ResumeParsingOutput {
  summary: string
  skills: string[]
  experience: ExperienceEntry[]
  projects: string[]
  certifications: string[]
  education: string[]
  name: string
  phone: string
  email: string
  linkedin: string
  github: string
}

export interface GapAnalysisOutput {
  missing_skills: string[]
  weak_skills: string[]
  strong_matches: string[]
  recommended_emphasis: string[]
  keyword_strategy: string[]
  bullet_point_improvement_plan: string[]
  tone_guidance: string
}

export interface RewriteOutput {
  summary: string
  skills: string[]
  experience: ExperienceEntry[]
  projects: string[]
  certifications: string[]
  education: string[]
}

export interface ATSComplianceOutput {
  ats_score: number
  missing_keywords: string[]
  formatting_issues: string[]
  clarity_issues: string[]
  recommended_fixes: string[]
  auto_fixes_applied: string[]
  final_resume: string
}

export interface TonePolishingOutput {
  polished_resume: string
}

export interface CoverLetterOutput {
  cover_letter: string
}

export type StageResult<T> = T | Record<string, unknown> | null

export interface PipelineRunResponse {
  parsed_job_description: StageResult<JDParsingOutput>
  parsed_resume: StageResult<ResumeParsingOutput>
  tailoring_strategy: StageResult<GapAnalysisOutput>
  rewritten_resume: StageResult<RewriteOutput>
  ats_optimized_resume: StageResult<ATSComplianceOutput>
  polished_resume: StageResult<TonePolishingOutput>
  cover_letter: StageResult<CoverLetterOutput>
  output_files: Record<string, string>
}