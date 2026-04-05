import { useQuery } from '@tanstack/react-query'
import { tasksApi } from '@/api/tasks'
import { POLL_INTERVAL_MS } from '@/lib/constants'
import type { Task } from '@/types'

export function useTaskPolling(taskId: string) {
  return useQuery<Task, Error>({
    queryKey: ['task', taskId],
    queryFn: () => tasksApi.get(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'COMPLETED' || status === 'FAILED') return false
      return POLL_INTERVAL_MS
    },
    staleTime: 0,
    enabled: !!taskId,
  })
}
