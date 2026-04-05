import { useEffect } from 'react'
import { Layout, Space, Tooltip, Popover, Typography, Badge } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/api/health'
import { useHealthStore } from '@/stores/healthStore'
import { HEALTH_POLL_INTERVAL_MS } from '@/lib/constants'
import type { HealthStatus } from '@/types'

const { Header } = Layout
const { Text } = Typography

function HealthPopoverContent({ health }: { health: HealthStatus }) {
  return (
    <Space direction="vertical" size={4} style={{ minWidth: 200 }}>
      {Object.entries(health.checks).map(([svc, check]) => (
        <Space key={svc} style={{ justifyContent: 'space-between', width: '100%' }}>
          <Text>{svc}</Text>
          <Space>
            <Badge
              status={check.status === 'ok' ? 'success' : 'error'}
              text={check.status}
            />
            <Text type="secondary">{check.latency_ms}ms</Text>
          </Space>
        </Space>
      ))}
      {health.dev_mode && <Text type="secondary" style={{ fontSize: 11 }}>DEV MODE</Text>}
    </Space>
  )
}

export function Topbar() {
  const { health, error, setHealth, setError } = useHealthStore()

  const { data } = useQuery<HealthStatus, Error>({
    queryKey: ['health'],
    queryFn: healthApi.get,
    refetchInterval: HEALTH_POLL_INTERVAL_MS,
  })

  useEffect(() => {
    if (data) setHealth(data)
  }, [data, setHealth])

  const allOk = health && Object.values(health.checks).every((c) => c.status === 'ok')
  const anyDegraded =
    health && Object.values(health.checks).some((c) => c.latency_ms > 100)

  const dotStatus = error ? 'error' : !health ? 'default' : !allOk ? 'error' : anyDegraded ? 'warning' : 'success'
  const dotText = error ? 'unreachable' : !health ? '…' : !allOk ? 'degraded' : 'healthy'

  return (
    <Header
      style={{
        background: '#fff',
        padding: '0 32px',
        borderBottom: '1px solid #f1f5f9',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        height: 64,
      }}
    >
      <Tooltip title="System health">
        <Popover
          content={health ? <HealthPopoverContent health={health} /> : 'Checking…'}
          title="Service Status"
          trigger="click"
          placement="bottomRight"
        >
          <div style={{ 
            padding: '4px 12px', 
            borderRadius: 20, 
            background: '#f8fafc', 
            border: '1px solid #e2e8f0',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <Badge status={dotStatus} />
            <Text style={{ fontSize: 13, color: '#64748b', fontWeight: 500 }}>System {dotText}</Text>
          </div>
        </Popover>
      </Tooltip>
    </Header>
  )
}
