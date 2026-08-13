/**
 * TypeScript mirrors of the FastAPI response models and the pipeline output
 * models.  Each interface notes the backend schema it mirrors so drift is easy
 * to spot when the backend adds or renames fields.
 *
 * Web API models mirror `app/schemas.py`; the agent output models mirror
 * `client/models.py` (serialized into the pipeline response).
 */

/**
 * `GET /api/models` row — from `config/agents.py: get_model_summary()`, mirrors
 * `app.schemas.ModelSummaryRow`. The effective `provider`/`model` are the
 * values after any persisted override; the `default_*` fields are the
 * environment defaults the agent would fall back to.
 */
export interface ModelSummary {
  agent: string
  provider: string
  model: string
  default_provider: string
  default_model: string
  is_overridden: boolean
}

/**
 * `PATCH /api/models/{agent}` body — mirrors `app.schemas.AgentOverrideUpdate`.
 * A `null` field leaves that dimension unchanged (inheriting the default).
 */
export interface AgentOverrideUpdate {
  provider?: string | null
  model?: string | null
}

export type TaskStatusName = 'pending' | 'running' | 'completed' | 'failed'

/** `POST /api/pipeline/async` response — mirrors `app.schemas.TaskCreated`. */
export interface TaskCreated {
  task_id: string
}

/** `GET /api/tasks/{task_id}` response — mirrors `app.schemas.TaskStatus`. */
export interface TaskStatus {
  status: TaskStatusName
  result?: Record<string, unknown> | null
  error?: string | null
  created_at?: number | null
  completed_at?: number | null
}

/** One file row — mirrors `app.schemas.FileMeta`. */
export interface FileMeta {
  name: string
  size: number
  modified: string
  type: string
  path: string
}

/** `GET /api/files/{generated|uploaded}` response — mirrors `app.schemas.PagedFile`. */
export interface PagedFile {
  items: FileMeta[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

/** `DELETE /api/files` response — mirrors `app.schemas.DeleteFilesResponse`. */
export interface DeleteFilesResponse {
  deleted: string[]
  missing: string[]
}

/** One work-history entry — mirrors `client.models.ExperienceEntry`. */
export interface ExperienceEntry {
  title?: string
  company?: string
  dates?: string
  responsibilities?: string[]
  achievements?: string[]
  metrics?: string[]
}

/** Agent 1 output — mirrors `client.models.JDParsingOutput`. */
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

/** Agent 2 output — mirrors `client.models.ResumeParsingOutput`. */
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

/** Agent 3 output — mirrors `client.models.GapAnalysisOutput`. */
export interface GapAnalysisOutput {
  missing_skills: string[]
  weak_skills: string[]
  strong_matches: string[]
  recommended_emphasis: string[]
  keyword_strategy: string[]
  bullet_point_improvement_plan: string[]
  tone_guidance: string
}

/** Agent 4 output — mirrors `client.models.RewriteOutput`. */
export interface RewriteOutput {
  summary: string
  skills: string[]
  experience: ExperienceEntry[]
  projects: string[]
  certifications: string[]
  education: string[]
}

/** Agent 5 output — mirrors `client.models.ATSComplianceOutput`. */
export interface ATSComplianceOutput {
  ats_score: number
  missing_keywords: string[]
  formatting_issues: string[]
  clarity_issues: string[]
  recommended_fixes: string[]
  auto_fixes_applied: string[]
  final_resume: string
}

/** Agent 6 output — mirrors `client.models.TonePolishingOutput`. */
export interface TonePolishingOutput {
  polished_resume: string
}

/** Agent 7 output — mirrors `client.models.CoverLetterOutput`. */
export interface CoverLetterOutput {
  cover_letter: string
}

/**
 * A pipeline stage's result: the typed output, an arbitrary dict when the
 * backend returned an unexpected shape, or `null` when the stage produced no
 * result.  Mirrors the `Any`-typed fields of `app.schemas.PipelineRunResponse`.
 */
export type StageResult<T> = T | Record<string, unknown> | null

/** `POST /api/pipeline` response — mirrors `app.schemas.PipelineRunResponse`. */
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