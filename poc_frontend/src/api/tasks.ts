import { apiClient } from './client'
import type {
  Task,
  TaskListResponse,
  LogsResponse,
  CreateTaskPayload,
  ListTasksParams,
} from '@/types'

export const tasksApi = {
  create: (payload: CreateTaskPayload) =>
    apiClient.post<Task>('/api/v1/tasks', payload).then((r) => r.data),

  list: (params: ListTasksParams = {}) =>
    apiClient
      .get<TaskListResponse>('/api/v1/tasks', { params })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Task>(`/api/v1/tasks/${id}`).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/tasks/${id}`).then((r) => r.data),

  getLogs: (id: string, params?: { limit?: number; cursor?: string }) =>
    apiClient
      .get<LogsResponse>(`/api/v1/tasks/${id}/logs`, { params })
      .then((r) => r.data),
}
