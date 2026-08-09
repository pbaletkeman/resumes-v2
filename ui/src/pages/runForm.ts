export interface RunInputs {
  jobDescription: string
  resume: string
  jobFile: File | null
  resumeFile: File | null
  candidateName: string
  companyName: string
}

export function validateRunInputs(inputs: RunInputs): string | null {
  if (inputs.jobDescription.trim() === '' && inputs.jobFile === null) {
    return 'Provide a job description as pasted text or an uploaded file.'
  }
  if (inputs.resume.trim() === '' && inputs.resumeFile === null) {
    return 'Provide a resume as pasted text or an uploaded file.'
  }
  return null
}

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