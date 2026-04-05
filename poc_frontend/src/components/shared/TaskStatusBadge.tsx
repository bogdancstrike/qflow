import { Badge, Tag } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'
import type { TaskStatus } from '@/types'
import { STATUS_COLORS } from '@/lib/constants'

interface Props {
  status: TaskStatus
  showDot?: boolean
}

export function TaskStatusBadge({ status, showDot = false }: Props) {
  const color = STATUS_COLORS[status] ?? 'default'

  if (showDot && (status === 'PENDING' || status === 'RUNNING')) {
    return (
      <Tag
        icon={<LoadingOutlined spin />}
        color={color}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
      >
        {status}
      </Tag>
    )
  }

  return (
    <Tag color={color} variant="filled">
      {status}
    </Tag>
  )
}

export function HealthDot({ ok, latencyMs }: { ok: boolean; latencyMs: number }) {
  return (
    <Badge
      status={ok ? (latencyMs > 100 ? 'warning' : 'success') : 'error'}
      text={ok ? (latencyMs > 100 ? 'degraded' : 'ok') : 'down'}
    />
  )
}
