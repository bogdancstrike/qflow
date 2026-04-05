import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme } from 'antd'
import { AppShell } from '@/components/layout/AppShell'
import { HomePage } from '@/pages/HomePage'
import { DashboardPage } from '@/pages/DashboardPage'
import { TaskListPage } from '@/pages/TaskListPage'
import { TaskDetailPage } from '@/pages/TaskDetailPage'
import { FlowCataloguePage } from '@/pages/FlowCataloguePage'
import { useThemeStore } from '@/stores/themeStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  const { mode } = useThemeStore()
  const isDark = mode === 'dark'

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff', // Classic Ant Pro Blue
          borderRadius: 4, // Tighter corners for 'Pro' look
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          colorBgLayout: isDark ? '#141414' : '#f0f2f5',
          fontSize: 14,
          colorTextHeading: isDark ? '#d9d9d9' : '#1f1f1f',
          colorTextSecondary: isDark ? '#8c8c8c' : '#8c8c8c',
        },
        components: {
          Layout: {
            headerBg: isDark ? '#1f1f1f' : '#ffffff',
            siderBg: isDark ? '#1f1f1f' : '#ffffff',
          },
          Card: {
            boxShadowTertiary: isDark 
              ? '0 1px 2px 0 rgba(0, 0, 0, 0.5), 0 1px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px 0 rgba(0, 0, 0, 0.4)'
              : '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
          },
          Menu: {
            itemSelectedBg: isDark ? '#111b26' : '#e6f7ff',
            itemSelectedColor: '#1890ff',
            itemHeight: 40,
          },
          Table: {
            headerBg: isDark ? '#1d1d1d' : '#fafafa',
            headerColor: isDark ? '#8c8c8c' : '#595959',
            headerBorderRadius: 2,
          },
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/submit" element={<HomePage />} />
              <Route path="/tasks" element={<TaskListPage />} />
              <Route path="/tasks/:id" element={<TaskDetailPage />} />
              <Route path="/flows" element={<FlowCataloguePage />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  )
}
