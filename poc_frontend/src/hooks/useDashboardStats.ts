import { useQuery } from '@tanstack/react-query'
import { tasksApi } from '@/api/tasks'
import type { Task, TaskStatus } from '@/types'

export interface DashboardStats {
  total: number
  byStatus: Record<TaskStatus, number>
  byInputType: Record<string, number>
  outputUsage: Record<string, number>
  avgDurationMs: number
  p95DurationMs: number
  successRate: number
  timeSeriesLast7d: { date: string; count: number; status: TaskStatus }[]
  hourlyVolume24h: { hour: string; count: number; status: TaskStatus }[]
  durationByInputType: { type: string; avgMs: number }[]
  concurrencyPeak24h: { time: string; count: number }[]
  inputSuccessRate: { type: string; rate: number }[]
  recentTasks: Task[]
}

function durationMs(task: Task): number | null {
  if (task.status !== 'COMPLETED' && task.status !== 'FAILED') return null
  return new Date(task.updated_at).getTime() - new Date(task.created_at).getTime()
}

function percentile(arr: number[], p: number): number {
  if (!arr.length) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const idx = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.max(0, idx)]
}

export function useDashboardStats() {
  return useQuery<DashboardStats, Error>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      // Fetch up to 500 most recent tasks for better statistics
      const data = await tasksApi.list({ limit: 500, sort: 'created_at:desc' })
      const tasks = data.tasks

      const byStatus: Record<string, number> = { PENDING: 0, RUNNING: 0, COMPLETED: 0, FAILED: 0 }
      const byInputType: Record<string, number> = {}
      const outputUsage: Record<string, number> = {}
      const durations: number[] = []
      const durationsByType: Record<string, number[]> = {}
      const statusByType: Record<string, { total: number; success: number }> = {}

      tasks.forEach((t) => {
        byStatus[t.status] = (byStatus[t.status] ?? 0) + 1
        byInputType[t.input_type] = (byInputType[t.input_type] ?? 0) + 1
        t.outputs.forEach((o) => { outputUsage[o] = (outputUsage[o] ?? 0) + 1 })
        
        statusByType[t.input_type] = statusByType[t.input_type] || { total: 0, success: 0 }
        if (t.status === 'COMPLETED' || t.status === 'FAILED') {
          statusByType[t.input_type].total++
          if (t.status === 'COMPLETED') statusByType[t.input_type].success++
        }

        const d = durationMs(t)
        if (d !== null) {
          durations.push(d)
          durationsByType[t.input_type] = [...(durationsByType[t.input_type] ?? []), d]
        }
      })

      // Time series — last 7 days
      const now = new Date()
      const buckets7d: Record<string, Record<TaskStatus, number>> = {}
      for (let i = 6; i >= 0; i--) {
        const d = new Date(now.getTime() - i * 86400000)
        const key = d.toISOString().slice(0, 10)
        buckets7d[key] = { PENDING: 0, RUNNING: 0, COMPLETED: 0, FAILED: 0 }
      }

      // Time series — last 24 hours (hourly)
      const buckets24h: Record<string, Record<TaskStatus, number>> = {}
      for (let i = 23; i >= 0; i--) {
        const d = new Date(now.getTime() - i * 3600000)
        const key = d.toISOString().slice(0, 13) // YYYY-MM-DDTHH
        buckets24h[key] = { PENDING: 0, RUNNING: 0, COMPLETED: 0, FAILED: 0 }
      }

      tasks.forEach((t) => {
        const dayKey = t.created_at.slice(0, 10)
        const hourKey = t.created_at.slice(0, 13)
        if (buckets7d[dayKey]) buckets7d[dayKey][t.status]++
        if (buckets24h[hourKey]) buckets24h[hourKey][t.status]++
      })

      const timeSeriesLast7d: DashboardStats['timeSeriesLast7d'] = []
      Object.entries(buckets7d).forEach(([date, counts]) => {
        ;(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'] as TaskStatus[]).forEach((s) => {
          timeSeriesLast7d.push({ date, status: s, count: counts[s] })
        })
      })

      const hourlyVolume24h: DashboardStats['hourlyVolume24h'] = []
      Object.entries(buckets24h).forEach(([hour, counts]) => {
        ;(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'] as TaskStatus[]).forEach((s) => {
          hourlyVolume24h.push({ hour: hour.slice(11) + ':00', status: s, count: counts[s] })
        })
      })

      const durationByInputType = Object.entries(durationsByType).map(([type, ds]) => ({
        type,
        avgMs: Math.round(ds.reduce((a, b) => a + b, 0) / ds.length),
      }))

      const inputSuccessRate = Object.entries(statusByType).map(([type, stats]) => ({
        type,
        rate: stats.total ? Math.round((stats.success / stats.total) * 100) : 0
      }))

      // Simple Concurrency Simulation (Count overlapping tasks)
      const concurrencyPeak24h: { time: string; count: number }[] = []
      Object.entries(buckets24h).forEach(([hour, counts]) => {
        const active = counts.RUNNING + counts.PENDING
        concurrencyPeak24h.push({ time: hour.slice(11) + ':00', count: active })
      })

      const completed = byStatus['COMPLETED'] ?? 0
      const failed = byStatus['FAILED'] ?? 0
      const finished = completed + failed
      const successRate = finished ? Math.round((completed / finished) * 100) : 0

      return {
        total: tasks.length,
        byStatus: byStatus as Record<TaskStatus, number>,
        byInputType,
        outputUsage,
        avgDurationMs: durations.length ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0,
        p95DurationMs: percentile(durations, 95),
        successRate,
        timeSeriesLast7d,
        hourlyVolume24h,
        durationByInputType,
        concurrencyPeak24h,
        inputSuccessRate,
        recentTasks: tasks.slice(0, 10),
      }
    },
    refetchInterval: 10000,
    staleTime: 5000,
  })
}
