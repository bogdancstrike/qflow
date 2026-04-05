import { useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Typography, Space } from 'antd'
import {
  HomeOutlined,
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
  const location = useLocation()
  const navigate = useNavigate()

  const selectedKey =
    NAV_ITEMS.slice()
      .reverse()
      .find((item) => location.pathname.startsWith(item.key) || location.pathname === item.key)
      ?.key ?? '/dashboard'

  return (
    <Sider
      width={240}
      theme="light"
      style={{
        borderRight: '1px solid #f1f5f9',
        overflow: 'auto',
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      <div style={{ padding: '24px 24px 16px' }}>
        <Space size={12}>
          <div style={{
            width: 32,
            height: 32,
            background: '#2563eb',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 'bold',
            fontSize: 18
          }}>Q</div>
          <Title level={4} style={{ margin: 0, fontSize: 18, letterSpacing: '-0.025em' }}>
            QFlow AI
          </Title>
        </Space>
      </div>

      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        style={{ height: 'auto', borderRight: 0, paddingTop: 4 }}
        items={NAV_ITEMS}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  )
}
