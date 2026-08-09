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

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: fetchModels,
  })
}

export function useInvokePipeline() {
  return useMutation({
    mutationFn: runPipelineAsync,
  })
}

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

export function useFiles(kind: 'generated' | 'uploaded', params: FileListParams) {
  return useQuery({
    queryKey: ['files', kind, params],
    queryFn: () => listFiles(kind, params),
    placeholderData: keepPreviousData,
  })
}

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