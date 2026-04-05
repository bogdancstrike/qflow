import { apiClient } from './client'
import type { DashboardStats } from '@/types'

export const statsApi = {
  get: () =>
    apiClient.get<DashboardStats>('/api/v1/stats').then((r) => r.data),
}
