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
        padding: '0 24px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 56,
      }}
    >
      <Typography.Title level={4} style={{ margin: 0, fontSize: 18 }}>
        QFlow AI Orchestrator
      </Typography.Title>

      <Tooltip title="System health">
        <Popover
          content={health ? <HealthPopoverContent health={health} /> : 'Checking…'}
          title="Service Status"
          trigger="click"
        >
          <Badge status={dotStatus} text={dotText} style={{ cursor: 'pointer' }} />
        </Popover>
      </Tooltip>
    </Header>
  )
}
