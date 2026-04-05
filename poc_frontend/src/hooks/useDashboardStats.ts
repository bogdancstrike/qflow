import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'
import { tasksApi } from '@/api/tasks'
import type { DashboardStats } from '@/types'
import { useThemeStore } from '@/stores/themeStore'

export function useDashboardStats() {
  const { mode } = useThemeStore()

  return useQuery<DashboardStats, Error>({
    queryKey: ['dashboard-stats', mode],
    queryFn: async () => {
      // 1. Get global aggregates from the new stats endpoint
      const stats = await statsApi.get()
      
      // 2. Get 10 most recent tasks for the activity list
      const recent = await tasksApi.list({ page: 1, size: 10, sort: 'created_at:desc' })
      
      return {
        ...stats,
        recentTasks: recent.tasks
      }
    },
    refetchInterval: 3000, // Faster refresh for real-time feel
    staleTime: 1000,
  })
}
