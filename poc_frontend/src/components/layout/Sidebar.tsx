import { useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  HomeOutlined,
  UnorderedListOutlined,
  BranchesOutlined,
} from '@ant-design/icons'

const { Sider } = Layout

const NAV_ITEMS = [
  { key: '/', label: 'Submit Task', icon: <HomeOutlined /> },
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
      ?.key ?? '/'

  return (
    <Sider
      width={200}
      style={{
        background: '#fff',
        borderRight: '1px solid #f0f0f0',
        overflow: 'auto',
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        style={{ height: '100%', borderRight: 0, paddingTop: 8 }}
        items={NAV_ITEMS}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  )
}
