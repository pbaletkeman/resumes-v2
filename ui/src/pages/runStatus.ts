/**
 * Pure status helpers for the Run page: map a background-pipeline task status
 * to its tag severity and human-readable label, and decide whether a task is
 * still active (not yet terminal). Kept free of React so the page can import
 * them and the unit tests can cover them directly.
 */
import type { TaskStatus, TaskStatusName } from '../api/types'

/** Tag severity per task status, matching the Run page status panel. */
export const STATUS_SEVERITY: Record<TaskStatus['status'], 'info' | 'success' | 'danger'> = {
  pending: 'info',
  running: 'info',
  completed: 'success',
  failed: 'danger',
}

/** Human-readable label per task status, shown on the status tag. */
export const TASK_STATUS_LABEL: Record<TaskStatus['status'], string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
}

/**
 * True while a task has not yet reached a terminal state: no status is known
 * yet (task created but not polled), pending, or running.
 */
export function isTaskActive(status: TaskStatusName | undefined): boolean {
  return status === undefined || status === 'pending' || status === 'running'
}

/**
 * Human-readable label; treats an unknown status as "Pending" (not polled
 * yet).
 */
export function taskStatusLabel(status: TaskStatusName | undefined): string {
  return status === undefined ? 'Pending' : TASK_STATUS_LABEL[status]
}