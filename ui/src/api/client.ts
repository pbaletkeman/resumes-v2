/**
 * Thin fetch wrapper for the FastAPI backend (`/api` base path).
 *
 * Every endpoint returns typed JSON via `apiFetch`, which converts non-2xx
 * responses into thrown `Error`s using the backend's `detail` field
 * (see `parseErrorDetail`).  Used by the hooks in `hooks.ts`; pages never
 * call these functions directly.
 */
import type {
  DeleteFilesResponse,
  ModelSummary,
  PagedFile,
  TaskCreated,
  TaskStatus,
} from './types'

const API_BASE = '/api'

export type FileListParams = {
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

/**
 * Return a plain-string error `detail` unchanged, or `null` if it is not a
 * string.  FastAPI validation errors come back as `detail: string` (e.g. our
 * own `400` messages), so this is the fast path.
 */
function _detailString(detail: unknown): string | null {
  return typeof detail === 'string' ? detail : null
}

/**
 * Join a FastAPI validation-style `detail` array into a single message.
 *
 * Each element may be a bare string or an object carrying a `msg` field
 * (Pydantic's `{"loc": [...], "msg": "...", "type": "..."}` shape).  Non-string
 * elements without a `msg` are skipped.  Returns `null` when `detail` is not an
 * array or yields no usable messages.
 */
function _detailArray(detail: unknown): string | null {
  if (!Array.isArray(detail)) {
    return null
  }
  const messages = detail
    .map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'msg' in item) {
        return String((item as { msg: unknown }).msg)
      }
      return null
    })
    .filter((m): m is string => m !== null)
  return messages.length > 0 ? messages.join('; ') : null
}

async function parseErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return _detailString(body.detail) ?? _detailArray(body.detail)
  } catch {
    return null
  }
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