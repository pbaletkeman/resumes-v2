import { useCallback, useRef, useState } from 'react'
import { Button } from 'primereact/button'
import { FileUpload } from 'primereact/fileupload'
import { InputText } from 'primereact/inputtext'
import { InputTextarea } from 'primereact/inputtextarea'
import { ProgressSpinner } from 'primereact/progressspinner'
import { Tag } from 'primereact/tag'
import { useInvokePipeline, usePollTask } from '../api/hooks'
import type { TaskStatus } from '../api/types'
import { useToast } from '../toast/ToastContext'
import { buildRunFormData, validateRunInputs } from './runForm'
import ResultsTabView from './results/ResultsTabView'

interface FileChosenProps {
  file: File | null
  onChange: (file: File | null) => void
}

function FileChosen({ file, onChange }: FileChosenProps) {
  const fileUploadRef = useRef<FileUpload>(null)

  return (
    <div className="run-file">
      {file === null ? (
        <FileUpload
          ref={fileUploadRef}
          mode="basic"
          accept=".txt,.docx,.pdf"
          chooseLabel="Choose file"
          auto={false}
          customUpload
          onSelect={(e) => onChange(e.files[0] ?? null)}
        />
      ) : (
        <>
          <span className="run-file-name">
            <i className="pi pi-file" />
            {file.name}
          </span>
          <Button
            type="button"
            icon="pi pi-times"
            rounded
            text
            severity="danger"
            onClick={() => {
              fileUploadRef.current?.clear()
              onChange(null)
            }}
            aria-label="Remove file"
          />
        </>
      )}
    </div>
  )
}

const STATUS_SEVERITY: Record<TaskStatus['status'], 'info' | 'success' | 'danger'> = {
  pending: 'info',
  running: 'info',
  completed: 'success',
  failed: 'danger',
}

function RunPage() {
  const [jobDescription, setJobDescription] = useState('')
  const [resume, setResume] = useState('')
  const [jobFile, setJobFile] = useState<File | null>(null)
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [candidateName, setCandidateName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [taskId, setTaskId] = useState<string | null>(null)
  const { show } = useToast()
  const invokePipeline = useInvokePipeline()

  const handleTaskDone = useCallback(
    (status: TaskStatus) => {
      if (status.status === 'failed') {
        show({
          severity: 'error',
          summary: 'Pipeline failed',
          detail: status.error ?? 'Unknown pipeline error',
        })
      }
    },
    [show],
  )

  const taskQuery = usePollTask(taskId, handleTaskDone)
  const status = taskQuery.data?.status
  const taskError = taskQuery.data?.error

  const active =
    invokePipeline.isPending ||
    (taskId !== null &&
      (status === undefined || status === 'pending' || status === 'running'))

  function resetTask() {
    setTaskId(null)
  }

  function handleSubmit() {
    const inputs = { jobDescription, resume, jobFile, resumeFile, candidateName, companyName }
    const invalid = validateRunInputs(inputs)
    if (invalid !== null) {
      show({ severity: 'warn', summary: 'Missing input', detail: invalid })
      return
    }
    invokePipeline.mutate(
      buildRunFormData(inputs),
      {
        onSuccess: (data) => setTaskId(data.task_id),
        onError: (error) => {
          show({ severity: 'error', summary: 'Pipeline failed', detail: error.message })
        },
      },
    )
  }

  return (
    <section className="run-page">
      <h1>Run Pipeline</h1>
      <div className="run-grid">
        <div className="run-column">
          <label className="p-text-secondary" htmlFor="job-description">
            Job Description
          </label>
          <InputTextarea
            id="job-description"
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            rows={12}
            autoResize={false}
            placeholder="Paste the job description, or upload a file below."
          />
          <FileChosen file={jobFile} onChange={setJobFile} />
        </div>
        <div className="run-column">
          <label className="p-text-secondary" htmlFor="resume">
            Resume
          </label>
          <InputTextarea
            id="resume"
            value={resume}
            onChange={(e) => setResume(e.target.value)}
            rows={12}
            autoResize={false}
            placeholder="Paste the resume, or upload a file below."
          />
          <FileChosen file={resumeFile} onChange={setResumeFile} />
        </div>
      </div>
      <div className="run-options">
        <span className="p-float-label">
          <InputText
            id="candidate-name"
            value={candidateName}
            onChange={(e) => setCandidateName(e.target.value)}
          />
          <label htmlFor="candidate-name">Candidate name (optional)</label>
        </span>
        <span className="p-float-label">
          <InputText
            id="company-name"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
          />
          <label htmlFor="company-name">Company name (optional)</label>
        </span>
      </div>
      <div className="run-actions">
        <Button
          label={
            active && status === 'running' ? 'Running...' : active ? 'Starting...' : 'Run Pipeline'
          }
          icon={active ? 'pi pi-spin pi-spinner' : 'pi pi-play'}
          onClick={handleSubmit}
          disabled={active}
        />
        {taskId !== null && (
          <Button
            type="button"
            label="Reset"
            icon="pi pi-refresh"
            severity="secondary"
            onClick={resetTask}
            disabled={active}
          />
        )}
      </div>
      {taskId !== null && (
        <div className="run-status">
          <div className="run-status-label">
            <span className="p-text-secondary">Task</span>
            <code>{taskId}</code>
          </div>
          {status === undefined || status === 'pending' || status === 'running' ? (
            <div className="run-status-active">
              <ProgressSpinner style={{ width: '2rem', height: '2rem' }} strokeWidth="4" />
              <Tag value={status ?? 'pending'} severity="info" />
            </div>
          ) : (
            <div className="run-status-active">
              <Tag value={status ?? 'completed'} severity={STATUS_SEVERITY[status ?? 'completed']} />
            </div>
          )}
          {status === 'failed' && taskError && (
            <div className="run-status-error">{taskError}</div>
          )}
        </div>
      )}
      {status === 'completed' && (
        <ResultsTabView result={taskQuery.data?.result ?? null} />
      )}
    </section>
  )
}

export default RunPage