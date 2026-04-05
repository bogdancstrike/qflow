import { Layout, theme } from 'antd'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

const { Content } = Layout

export function AppShell() {
  const { token } = theme.useToken()
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout>
        <Sidebar />
        <Layout>
          <Topbar />
          <Content style={{ 
            padding: '24px', 
            background: token.colorBgLayout, 
            minHeight: 'calc(100vh - 64px)',
            overflowY: 'auto'
          }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}
