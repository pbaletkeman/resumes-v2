/**
 * Pure form logic for the Run page: describes the pipeline inputs, validates
 * them, and builds the multipart FormData sent to ``POST /api/pipeline/async``.
 *
 * Precedence rule: **pasted text wins over an uploaded file** for both the job
 * description and the resume. This mirrors the backend resolver
 * ``app.main._read_text_input``, which returns the pasted text whenever it is
 * non-empty and only falls back to the uploaded file, so the frontend and the
 * backend never disagree about which input is used.
 */

/** Everything the Run page collects for a single pipeline run. */
export interface RunInputs {
  jobDescription: string
  resume: string
  jobFile: File | null
  resumeFile: File | null
  candidateName: string
  companyName: string
}

/**
 * Check that a run has both a job description and a resume.
 *
 * Each of the two required inputs counts as supplied when the pasted text is
 * non-empty OR a matching file has been chosen.
 *
 * Args:
 *   inputs: The raw form inputs from the Run page.
 *
 * Returns:
 *   ``null`` when the inputs are valid, otherwise a human-readable message
 *   describing the first missing input.
 */
export function validateRunInputs(inputs: RunInputs): string | null {
  if (inputs.jobDescription.trim() === '' && inputs.jobFile === null) {
    return 'Provide a job description as pasted text or an uploaded file.'
  }
  if (inputs.resume.trim() === '' && inputs.resumeFile === null) {
    return 'Provide a resume as pasted text or an uploaded file.'
  }
  return null
}

/**
 * Build the multipart form data for a pipeline run.
 *
 * Applies the "text wins over file" rule per field (matching the backend
 * ``_read_text_input``): if pasted text is non-empty it is appended under the
 * text field name and the file is skipped; otherwise the chosen file is
 * appended under its field name. Optional candidate/company names are appended
 * only when non-empty.
 *
 * Args:
 *   inputs: The raw form inputs from the Run page.
 *
 * Returns:
 *   A FormData ready to send to the pipeline endpoint.
 */
export function buildRunFormData(inputs: RunInputs): FormData {
  const formData = new FormData()
  const jd = inputs.jobDescription.trim()
  const resume = inputs.resume.trim()
  if (jd !== '') {
    formData.append('job_description', jd)
  } else if (inputs.jobFile !== null) {
    formData.append('job_file', inputs.jobFile)
  }
  if (resume !== '') {
    formData.append('resume', resume)
  } else if (inputs.resumeFile !== null) {
    formData.append('resume_file', inputs.resumeFile)
  }
  const candidateName = inputs.candidateName.trim()
  if (candidateName !== '') {
    formData.append('candidate_name', candidateName)
  }
  const companyName = inputs.companyName.trim()
  if (companyName !== '') {
    formData.append('company_name', companyName)
  }
  return formData
}