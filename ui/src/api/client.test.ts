/**
 * Unit tests for the API layer: the ``runForm.ts`` pure form builders
 * (text-over-file precedence, validation), the ``client.ts`` fetch wrappers
 * (endpoints, query-string building, error-detail parsing), and the
 * ``download.ts`` URL helpers.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildRunFormData,
  validateRunInputs,
  type RunInputs,
} from '../pages/runForm'
import { fileDownloadUrl, outputDownloadUrl } from './download'
import {
  deleteFiles,
  fetchModels,
  getTask,
  listFiles,
  runPipelineAsync,
} from './client'
import type { FileListParams } from './client'

function makeResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response
}

function makeJobFile(name = 'jd.txt'): File {
  return new File(['job description text'], name, { type: 'text/plain' })
}

function makeRunInputs(overrides: Partial<RunInputs> = {}): RunInputs {
  return {
    jobDescription:
      'Company is hiring a senior frontend engineer. Five years of React.',
    resume: 'Experienced React developer with TypeScript.',
    jobFile: null,
    resumeFile: null,
    candidateName: '',
    companyName: '',
    ...overrides,
  }
}

describe('buildRunFormData', () => {
  it('appends text fields when present', () => {
    const formData = buildRunFormData(
      makeRunInputs({ candidateName: 'Ada', companyName: 'Example Co' }),
    )
    expect(formData.get('job_description')).toBe(
      'Company is hiring a senior frontend engineer. Five years of React.',
    )
    expect(formData.get('resume')).toBe('Experienced React developer with TypeScript.')
    expect(formData.get('candidate_name')).toBe('Ada')
    expect(formData.get('company_name')).toBe('Example Co')
    expect(formData.get('job_file')).toBeNull()
    expect(formData.get('resume_file')).toBeNull()
  })

  it('omits empty text fields', () => {
    const formData = buildRunFormData(makeRunInputs())
    expect(formData.get('candidate_name')).toBeNull()
    expect(formData.get('company_name')).toBeNull()
  })

  it('falls back to the uploaded file when text is empty', () => {
    const jobFile = makeJobFile()
    const resumeFile = makeJobFile('resume.txt')
    const formData = buildRunFormData(
      makeRunInputs({
        jobDescription: '   ',
        resume: '',
        jobFile,
        resumeFile,
      }),
    )
    expect(formData.get('job_description')).toBeNull()
    expect(formData.get('job_file')).toBe(jobFile)
    expect(formData.get('resume')).toBeNull()
    expect(formData.get('resume_file')).toBe(resumeFile)
  })

  it('prefers text over an uploaded file', () => {
    const formData = buildRunFormData(
      makeRunInputs({ jobFile: makeJobFile(), resumeFile: makeJobFile('resume.txt') }),
    )
    const jd = formData.get('job_description')
    const resume = formData.get('resume')
    expect(typeof jd).toBe('string')
    expect(jd !== '').toBe(true)
    expect(typeof resume).toBe('string')
    expect(resume !== '').toBe(true)
    expect(formData.get('job_file')).toBeNull()
    expect(formData.get('resume_file')).toBeNull()
  })
})

describe('validateRunInputs', () => {
  it('returns null when both job and resume inputs exist', () => {
    expect(validateRunInputs(makeRunInputs())).toBeNull()
  })

  it('warns when job description is empty and no file is uploaded', () => {
    expect(
      validateRunInputs(
        makeRunInputs({ jobDescription: '  ', jobFile: null }),
      ) ?? '',
    ).toMatch(/job description/i)
  })

  it('warns when resume is empty and no file is uploaded', () => {
    expect(
      validateRunInputs(makeRunInputs({ resume: '', resumeFile: null })) ?? '',
    ).toMatch(/resume/i)
  })
})

describe('api client', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchModels GETs /api/models and parses JSON', async () => {
    const models = [{ agent: 'jd_parsing_agent', provider: 'ollama', model: 'qwen' }]
    fetchMock.mockResolvedValue(makeResponse(models))
    await expect(fetchModels()).resolves.toEqual(models)
    expect(fetchMock).toHaveBeenCalledWith('/api/models', undefined)
  })

  it('runPipelineAsync POSTs the FormData to /api/pipeline/async', async () => {
    const formData = buildRunFormData(makeRunInputs())
    fetchMock.mockResolvedValue(makeResponse({ task_id: 'task-123' }))
    await expect(runPipelineAsync(formData)).resolves.toEqual({
      task_id: 'task-123',
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/pipeline/async', {
      method: 'POST',
      body: formData,
    })
  })

  it('getTask GETs the encoded task URL', async () => {
    fetchMock.mockResolvedValue(makeResponse({ status: 'completed' }))
    await expect(getTask('abc/123')).resolves.toEqual({ status: 'completed' })
    expect(fetchMock).toHaveBeenCalledWith('/api/tasks/abc%2F123', undefined)
  })

  it('listFiles GETs /api/files/generated with only set query params', async () => {
    fetchMock.mockResolvedValue(
      makeResponse({ items: [], page: 2, page_size: 20, total: 0, total_pages: 0 }),
    )
    const params: FileListParams = { q: 'cover', page: 2 }
    await listFiles('generated', params)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/files/generated?q=cover&page=2',
      undefined,
    )
  })

  it('listFiles omits the query string when no params are set', async () => {
    fetchMock.mockResolvedValue(
      makeResponse({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }),
    )
    await listFiles('uploaded')
    expect(fetchMock).toHaveBeenCalledWith('/api/files/uploaded', undefined)
  })

  it('deleteFiles DELETEs /api/files with a JSON body', async () => {
    fetchMock.mockResolvedValue(makeResponse({ deleted: ['a.md'], missing: [] }))
    await expect(
      deleteFiles(['output/a.md', 'output/b.md']),
    ).resolves.toEqual({ deleted: ['a.md'], missing: [] })
    expect(fetchMock).toHaveBeenCalledWith('/api/files', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: ['output/a.md', 'output/b.md'] }),
    })
  })

  it('surfaces the backend detail message on non-2xx', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'boom' }, false, 500))
    await expect(fetchModels()).rejects.toThrow('boom')
  })

  it('joins validation-style detail arrays', async () => {
    fetchMock.mockResolvedValue(
      makeResponse(
        { detail: [{ msg: 'first' }, { msg: 'second' }] },
        false,
        422,
      ),
    )
    await expect(fetchModels()).rejects.toThrow('first; second')
  })

  it('falls back to a status message when detail is missing', async () => {
    fetchMock.mockResolvedValue(makeResponse({}, false, 404))
    await expect(fetchModels()).rejects.toThrow('Request failed with status 404')
  })
})

describe('download url helpers', () => {
  it('outputDownloadUrl encodes the file name', () => {
    expect(outputDownloadUrl('a b.md')).toBe('/api/outputs/a%20b.md')
  })

  it('fileDownloadUrl strips an output directory prefix', () => {
    expect(fileDownloadUrl('output\\2026\\resume.md')).toBe(
      '/api/outputs/resume.md',
    )
    expect(fileDownloadUrl('output/cover_letter.md')).toBe(
      '/api/outputs/cover_letter.md',
    )
  })
})