import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Statistic, Table, Tag, Space, Typography, Spin, Alert, Badge,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  ThunderboltOutlined, RiseOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import {
  Pie, Column, Bar, type PieConfig, type ColumnConfig, type BarConfig,
} from '@ant-design/plots'
import type { ColumnsType } from 'antd/es/table'
import { useDashboardStats } from '@/hooks/useDashboardStats'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { OUTPUT_LABELS, STATUS_COLORS } from '@/lib/constants'
import { formatMs, formatRelativeTime, inputPreview } from '@/lib/formatters'
import type { Task, OutputType } from '@/types'

const { Title, Text } = Typography

const STATUS_PIE_COLORS: Record<string, string> = {
  COMPLETED: '#52c41a',
  FAILED: '#ff4d4f',
  RUNNING: '#1677ff',
  PENDING: '#faad14',
}

const SERIES_COLORS: Record<string, string> = {
  COMPLETED: '#52c41a',
  FAILED: '#ff4d4f',
  RUNNING: '#1677ff',
  PENDING: '#faad14',
}

function StatCard({
  title, value, suffix, icon, color, loading,
}: {
  title: string
  value: string | number
  suffix?: string
  icon: React.ReactNode
  color: string
  loading?: boolean
}) {
  return (
    <Card size="small" style={{ height: '100%' }}>
      <Statistic
        title={
          <Space>
            <span style={{ color }}>{icon}</span>
            {title}
          </Space>
        }
        value={value}
        suffix={suffix}
        loading={loading}
        valueStyle={{ fontSize: 28, fontWeight: 700 }}
      />
    </Card>
  )
}

const RECENT_COLS: ColumnsType<Task> = [
  {
    title: 'ID',
    dataIndex: 'id',
    width: 110,
    render: (v: string) => <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}</Text>,
  },
  {
    title: 'Type',
    dataIndex: 'input_type',
    width: 110,
    render: (v: string) => <Tag>{v}</Tag>,
  },
  {
    title: 'Input',
    dataIndex: 'input_data',
    ellipsis: true,
    render: (v: Record<string, unknown>) => (
      <Text type="secondary" style={{ fontSize: 12 }}>{inputPreview(v)}</Text>
    ),
  },
  {
    title: 'Outputs',
    dataIndex: 'outputs',
    width: 180,
    render: (v: OutputType[]) => (
      <Space wrap size={2}>
        {v.map((o) => <Tag key={o} style={{ fontSize: 10, margin: 0 }}>{OUTPUT_LABELS[o]}</Tag>)}
      </Space>
    ),
  },
  {
    title: 'Status',
    dataIndex: 'status',
    width: 110,
    render: (v: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED') => <TaskStatusBadge status={v} showDot />,
  },
  {
    title: 'Age',
    dataIndex: 'created_at',
    width: 90,
    render: (v: string) => <Text style={{ fontSize: 12 }}>{formatRelativeTime(v)}</Text>,
  },
]

export function DashboardPage() {
  const { data: stats, isLoading, error } = useDashboardStats()
  const navigate = useNavigate()

  if (error) return <Alert type="error" message={error.message} />

  const pieData = stats
    ? Object.entries(stats.byStatus)
        .filter(([, v]) => v > 0)
        .map(([status, value]) => ({ status, value }))
    : []

  const pieConfig: PieConfig = {
    data: pieData,
    angleField: 'value',
    colorField: 'status',
    radius: 0.75,
    innerRadius: 0.55,
    label: { text: 'status', style: { fontSize: 12 } },
    legend: { color: { position: 'bottom' } },
    color: ({ status }: { status: string }) => STATUS_PIE_COLORS[status] ?? '#8c8c8c',
    annotations: stats
      ? [
          {
            type: 'text',
            style: {
              text: `${stats.total}`,
              x: '50%',
              y: '50%',
              textAlign: 'center',
              fontSize: 24,
              fontWeight: 700,
              fill: '#000',
            },
          },
          {
            type: 'text',
            style: {
              text: 'total',
              x: '50%',
              y: '62%',
              textAlign: 'center',
              fontSize: 12,
              fill: '#8c8c8c',
            },
          },
        ]
      : [],
  }

  const timeSeriesConfig: ColumnConfig = {
    data: stats?.timeSeriesLast7d ?? [],
    xField: 'date',
    yField: 'count',
    colorField: 'status',
    stack: true,
    color: ({ status }: { status: string }) => SERIES_COLORS[status] ?? '#8c8c8c',
    axis: { x: { label: { autoRotate: true } } },
    legend: { color: { position: 'top-right' } },
  }

  const durationConfig: BarConfig = {
    data: stats?.durationByInputType ?? [],
    xField: 'avgMs',
    yField: 'type',
    colorField: 'type',
    label: {
      text: (d: { avgMs: number }) => formatMs(d.avgMs),
      position: 'right',
      style: { fontSize: 12 },
    },
    axis: { x: { title: 'Avg duration (ms)' } },
    legend: false,
  }

  const outputUsageConfig: BarConfig = {
    data: stats
      ? Object.entries(stats.outputUsage).map(([output, count]) => ({
          output: OUTPUT_LABELS[output as OutputType] ?? output,
          count,
        }))
      : [],
    xField: 'count',
    yField: 'output',
    colorField: 'output',
    label: { text: 'count', position: 'right', style: { fontSize: 12 } },
    axis: { x: { title: 'Times requested' } },
    legend: false,
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>Dashboard</Title>

      {/* Stat cards */}
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Total Tasks"
            value={stats?.total ?? 0}
            icon={<UnorderedListOutlined />}
            color="#1677ff"
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Completed"
            value={stats?.byStatus.COMPLETED ?? 0}
            icon={<CheckCircleOutlined />}
            color="#52c41a"
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Failed"
            value={stats?.byStatus.FAILED ?? 0}
            icon={<CloseCircleOutlined />}
            color="#ff4d4f"
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Pending / Running"
            value={(stats?.byStatus.PENDING ?? 0) + (stats?.byStatus.RUNNING ?? 0)}
            icon={<ClockCircleOutlined />}
            color="#faad14"
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Success Rate"
            value={stats?.successRate ?? 0}
            suffix="%"
            icon={<RiseOutlined />}
            color="#52c41a"
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <StatCard
            title="Avg Duration"
            value={formatMs(stats?.avgDurationMs ?? 0)}
            icon={<ThunderboltOutlined />}
            color="#722ed1"
            loading={isLoading}
          />
        </Col>
      </Row>

      {/* Charts row 1 */}
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={8}>
          <Card title="Tasks by Status" size="small" style={{ height: 340 }}>
            {isLoading ? <Spin /> : <Pie {...pieConfig} height={260} />}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title="Tasks over Time (last 7 days)" size="small" style={{ height: 340 }}>
            {isLoading ? <Spin /> : <Column {...timeSeriesConfig} height={260} />}
          </Card>
        </Col>
      </Row>

      {/* Charts row 2 */}
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card title="Avg Duration by Input Type" size="small" style={{ height: 280 }}>
            {isLoading ? (
              <Spin />
            ) : stats?.durationByInputType.length === 0 ? (
              <Text type="secondary">No completed tasks yet</Text>
            ) : (
              <Bar {...durationConfig} height={200} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Output Type Usage" size="small" style={{ height: 280 }}>
            {isLoading ? <Spin /> : <Bar {...outputUsageConfig} height={200} />}
          </Card>
        </Col>
      </Row>

      {/* p95 callout */}
      {stats && stats.p95DurationMs > 0 && (
        <Card size="small" style={{ background: '#f0f5ff', border: '1px solid #adc6ff' }}>
          <Space>
            <ThunderboltOutlined style={{ color: '#2f54eb' }} />
            <Text>
              <Text strong>p95 duration: </Text>
              <Text code>{formatMs(stats.p95DurationMs)}</Text>
              {'  '}
              <Text type="secondary">across {stats.total} tasks (last 200)</Text>
            </Text>
          </Space>
        </Card>
      )}

      {/* Recent tasks */}
      <Card
        title="Recent Tasks"
        size="small"
        extra={
          <a onClick={() => navigate('/tasks')} style={{ fontSize: 13 }}>
            View all →
          </a>
        }
      >
        <Table
          dataSource={stats?.recentTasks ?? []}
          columns={RECENT_COLS}
          rowKey="id"
          size="small"
          pagination={false}
          loading={isLoading}
          onRow={(record) => ({ onClick: () => navigate(`/tasks/${record.id}`), style: { cursor: 'pointer' } })}
        />
      </Card>
    </Space>
  )
}
