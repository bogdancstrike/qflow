import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err.response?.data?.message ?? err.response?.data?.error ?? err.message ?? 'Unknown error'
    return Promise.reject(new Error(msg))
  },
)
