import { apiClient } from './client'
import type { FlowCatalogue } from '@/types'

export const flowsApi = {
  getCatalogue: () =>
    apiClient.get<FlowCatalogue>('/api/v1/flows').then((r) => r.data),
}
