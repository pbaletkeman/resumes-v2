import type {
  DeleteFilesResponse,
  ModelSummary,
  PagedFile,
  TaskCreated,
  TaskStatus,
} from './types'

const API_BASE = '/api'

export interface FileListParams {
  file_type?: string
  q?: string
  page?: number
  page_size?: number
  sort?: string
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      query.set(key, String(value))
    }
  }
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const detail = await parseErrorDetail(response)
    throw new Error(detail ?? `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

async function parseErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg)
          }
          return null
        })
        .filter((m): m is string => m !== null)
      if (messages.length > 0) return messages.join('; ')
    }
  } catch {
    return null
  }
  return null
}

export async function fetchModels(): Promise<ModelSummary[]> {
  return apiFetch<ModelSummary[]>('/models')
}

export async function runPipelineAsync(formData: FormData): Promise<TaskCreated> {
  return apiFetch<TaskCreated>('/pipeline/async', {
    method: 'POST',
    body: formData,
  })
}

export async function getTask(taskId: string): Promise<TaskStatus> {
  return apiFetch<TaskStatus>(`/tasks/${encodeURIComponent(taskId)}`)
}

export async function listFiles(
  kind: 'generated' | 'uploaded',
  params: FileListParams = {},
): Promise<PagedFile> {
  const query = buildQuery(params)
  return apiFetch<PagedFile>(`/files/${kind}${query}`)
}

export async function deleteFiles(files: string[]): Promise<DeleteFilesResponse> {
  return apiFetch<DeleteFilesResponse>('/files', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files }),
  })
}

export { API_BASE }