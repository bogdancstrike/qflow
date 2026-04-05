import { useQuery } from '@tanstack/react-query'
import { flowsApi } from '@/api/flows'
import type { FlowCatalogue } from '@/types'

export function useFlows() {
  return useQuery<FlowCatalogue, Error>({
    queryKey: ['flows'],
    queryFn: flowsApi.getCatalogue,
    staleTime: 60_000,
  })
}
