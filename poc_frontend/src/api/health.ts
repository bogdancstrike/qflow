import { apiClient } from './client'
import type { HealthStatus } from '@/types'

export const healthApi = {
  get: () => apiClient.get<HealthStatus>('/api/health').then((r) => r.data),
}
