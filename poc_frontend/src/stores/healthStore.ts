import { create } from 'zustand'
import type { HealthStatus } from '@/types'

interface HealthStore {
  health: HealthStatus | null
  error: boolean
  setHealth: (h: HealthStatus) => void
  setError: (v: boolean) => void
}

export const useHealthStore = create<HealthStore>((set) => ({
  health: null,
  error: false,
  setHealth: (h) => set({ health: h, error: false }),
  setError: (v) => set({ error: v }),
}))
