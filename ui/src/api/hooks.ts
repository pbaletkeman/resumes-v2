/**
 * React Query hooks wrapping the API client.
 *
 * Polling lifecycle: `useInvokePipeline` launches a background task and
 * returns its `task_id`; pages then feed that id into `usePollTask` (which
 * wraps `useTask`).  `useTask` polls every `POLL_INTERVAL_MS` while the task
 * is pending/running and stops once it reaches a terminal state.  When the
 * task settles, `usePollTask` invalidates the `['files']` queries so the file
 * list shows the freshly rendered outputs, then calls `onDone` so the page can
 * navigate/refresh.  `useFiles` / `useDeleteFiles` manage the generated and
 * uploaded file listings.
 */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect } from 'react'
import {
  deleteFiles,
  fetchModels,
  getTask,
  listFiles,
  runPipelineAsync,
  type FileListParams,
} from './client'
import type { ModelSummary, PagedFile, TaskStatus } from './types'

const POLL_INTERVAL_MS = 2000

/** Fetch the per-agent model summary shown on the home page. */
export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: fetchModels,
  })
}

/** Launch a background pipeline run; returns the created `task_id`. */
export function useInvokePipeline() {
  return useMutation({
    mutationFn: runPipelineAsync,
  })
}

/**
 * Poll a background pipeline task by id.
 *
 * The `refetchInterval` predicate polls only while the task is in a non-final
 * state (`pending` or `running`); it returns `false` once the task has
 * completed or failed so the query stops fetching.
 */
export function useTask(taskId: string | null) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTask(taskId ?? ''),
    enabled: taskId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? POLL_INTERVAL_MS : false
    },
  })
}

/**
 * Poll a task and react when it settles.
 *
 * Wraps `useTask` and, once the status is terminal (`completed` or `failed`):
 *
 * - invalidates the `['files']` queries — a completed run writes new files to
 *   `output/`, so the file listings would otherwise show stale data;
 * - fires `onDone(status)` exactly once per settling status so the page can
 *   show results or an error.
 */
export function usePollTask(
  taskId: string | null,
  onDone?: ((status: TaskStatus) => void) | null,
) {
  const queryClient = useQueryClient()
  const query = useTask(taskId)
  const status = query.data?.status

  useEffect(() => {
    if (
      status === undefined ||
      (status !== 'completed' && status !== 'failed')
    ) {
      return
    }
    queryClient.invalidateQueries({ queryKey: ['files'] })
    if (onDone && query.data) {
      onDone(query.data)
    }
  }, [onDone, query.data, queryClient, status])

  return query
}

/** Fetch a page of generated or uploaded files, keeping the previous page visible while refetching. */
export function useFiles(kind: 'generated' | 'uploaded', params: FileListParams) {
  return useQuery({
    queryKey: ['files', kind, params],
    queryFn: () => listFiles(kind, params),
    placeholderData: keepPreviousData,
  })
}

/** Delete files, then invalidate the file listings so they reflect the change. */
export function useDeleteFiles() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteFiles,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] })
    },
  })
}

export type { ModelSummary, PagedFile }