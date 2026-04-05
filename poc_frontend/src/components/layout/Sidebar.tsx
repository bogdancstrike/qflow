import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Typography, Space, theme } from 'antd'
import {
  UnorderedListOutlined,
  BranchesOutlined,
  DashboardOutlined,
  PlusCircleOutlined,
} from '@ant-design/icons'

const { Sider } = Layout
const { Title } = Typography

const NAV_ITEMS = [
  { key: '/dashboard', label: 'Dashboard', icon: <DashboardOutlined /> },
  { key: '/submit', label: 'Submit Task', icon: <PlusCircleOutlined /> },
  { key: '/tasks', label: 'Task List', icon: <UnorderedListOutlined /> },
  { key: '/flows', label: 'Flow Catalogue', icon: <BranchesOutlined /> },
]

export function Sidebar() {
  const { token } = theme.useToken()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const selectedKey =
    NAV_ITEMS.slice()
      .reverse()
      .find((item) => location.pathname.startsWith(item.key) || location.pathname === item.key)
      ?.key ?? '/dashboard'

  return (
    <Sider
      width={240}
      collapsible
      collapsed={collapsed}
      onCollapse={(value) => setCollapsed(value)}
      theme="light"
      style={{
        borderRight: `1px solid ${token.colorBorderSecondary}`,
        overflow: 'auto',
        height: '100vh',
        position: 'sticky',
        top: 0,
        background: token.colorBgContainer
      }}
    >
      <div style={{ padding: collapsed ? '24px 8px' : '24px 24px 16px', textAlign: collapsed ? 'center' : 'left' }}>
        <Space size={12} align="center">
          <div style={{
            width: 32,
            height: 32,
            background: token.colorPrimary,
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 'bold',
            fontSize: 18,
            flexShrink: 0
          }}>Q</div>
          {!collapsed && (
            <Title level={4} style={{ margin: 0, fontSize: 18, letterSpacing: '-0.025em', color: token.colorTextHeading }}>
              QFlow
            </Title>
          )}
        </Space>
      </div>

      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        style={{ height: 'auto', borderRight: 0, paddingTop: 4, background: 'transparent' }}
        items={NAV_ITEMS}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  )
}
