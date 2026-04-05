import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Table, Tag, Space, Typography, Spin, Alert, Button, Divider, Tooltip, Tabs, theme,
} from 'antd'
import {
  InfoCircleOutlined,
} from '@ant-design/icons'
import {
  Pie, Column, Bar, type PieConfig, type ColumnConfig, type BarConfig,
} from '@ant-design/plots'
import type { ColumnsType } from 'antd/es/table'
import { useDashboardStats } from '@/hooks/useDashboardStats'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { formatMs, formatRelativeTime, inputPreview, formatDuration } from '@/lib/formatters'
import type { Task, OutputType } from '@/types'
import { OUTPUT_LABELS } from '@/lib/constants'

const { Title, Text } = Typography

const STATUS_PIE_COLORS: Record<string, string> = {
  COMPLETED: '#52c41a',
  FAILED: '#f5222d',
  RUNNING: '#1890ff',
  PENDING: '#faad14',
}

function AnalysisCard({
  title, value, suffix, loading, footer,
}: {
  title: string
  value: string | number
  suffix?: string
  loading?: boolean
  footer?: React.ReactNode
}) {
  const { token } = theme.useToken()
  return (
    <Card variant="borderless" loading={loading} styles={{ body: { padding: '20px 24px 8px' } }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Text style={{ fontSize: 14, color: token.colorTextSecondary }}>{title}</Text>
        <Tooltip title="Task stats information">
          <InfoCircleOutlined style={{ color: token.colorTextDescription }} />
        </Tooltip>
      </div>
      <div style={{ margin: '4px 0 12px' }}>
        <Text style={{ fontSize: 30, color: token.colorTextHeading, fontWeight: 600 }}>
          {value}{suffix}
        </Text>
      </div>
      <div style={{ height: 16 }}>
        {/* Vertical spacing consistency */}
      </div>
      <Divider style={{ margin: '8px 0' }} />
      <div style={{ padding: '8px 0', fontSize: 14, color: token.colorTextSecondary }}>
        {footer}
      </div>
    </Card>
  )
}

const RECENT_COLS: ColumnsType<Task> = [
  {
    title: 'TASK ID',
    dataIndex: 'id',
    width: 100,
    render: (v: string) => <Text style={{ fontSize: 13, color: '#1890ff', fontWeight: 500 }}>{v.slice(0, 8).toUpperCase()}</Text>,
  },
  {
    title: 'TYPE',
    dataIndex: 'input_type',
    width: 100,
    render: (v: string) => <Text style={{ fontSize: 13, textTransform: 'uppercase' }}>{v}</Text>,
  },
  {
    title: 'CONTENT PREVIEW',
    dataIndex: 'input_data',
    ellipsis: true,
    render: (v: Record<string, unknown>) => (
      <Text type="secondary" style={{ fontSize: 13 }}>{inputPreview(v)}</Text>
    ),
  },
  {
    title: 'OUTPUTS',
    dataIndex: 'outputs',
    width: 200,
    render: (v: OutputType[]) => (
      <Space wrap size={4}>
        {v.map((o) => (
          <Tag key={o} variant="filled" style={{ fontSize: 10, margin: 0 }}>
            {OUTPUT_LABELS[o]}
          </Tag>
        ))}
      </Space>
    ),
  },
  {
    title: 'DURATION',
    key: 'duration',
    width: 100,
    render: (_: unknown, record: Task) =>
      record.status === 'COMPLETED' || record.status === 'FAILED'
        ? <Text style={{ fontSize: 12 }}>{formatDuration(record.created_at, record.updated_at)}</Text>
        : <Text type="secondary">—</Text>,
  },
  {
    title: 'STATUS',
    dataIndex: 'status',
    width: 120,
    render: (v: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED') => <TaskStatusBadge status={v} showDot />,
  },
  {
    title: 'AGE',
    dataIndex: 'created_at',
    width: 100,
    align: 'right',
    render: (v: string) => <Text style={{ fontSize: 12, color: '#8c8c8c' }}>{formatRelativeTime(v)}</Text>,
  },
]

export function DashboardPage() {
  const { data: stats, isLoading, error } = useDashboardStats()
  const navigate = useNavigate()
  const { token } = theme.useToken()

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
    radius: 0.8,
    innerRadius: 0.65,
    label: { text: 'value', style: { fontSize: 11, fontWeight: 600 } },
    legend: { color: { position: 'bottom' } },
    color: ({ status }: { status: string }) => STATUS_PIE_COLORS[status] ?? '#8c8c8c',
    annotations: stats
      ? [
          {
            type: 'text',
            style: {
              text: `${stats.total}`,
              x: '50%',
              y: '48%',
              textAlign: 'center',
              fontSize: 28,
              fontWeight: 600,
              fill: token.colorTextHeading,
            },
          },
          {
            type: 'text',
            style: {
              text: 'Tasks',
              x: '50%',
              y: '62%',
              textAlign: 'center',
              fontSize: 14,
              fill: token.colorTextSecondary,
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
    color: ({ status }: { status: string }) => STATUS_PIE_COLORS[status] ?? '#8c8c8c',
    axis: { x: { label: { autoRotate: true } } },
    legend: { color: { position: 'top', layout: { justifyContent: 'flex-end' } } },
  }

  const durationConfig: BarConfig = {
    data: stats?.durationByInputType ?? [],
    xField: 'avgMs',
    yField: 'type',
    colorField: 'type',
    label: {
      text: (d: { avgMs: number }) => formatMs(d.avgMs),
      position: 'right',
      style: { fontSize: 12, fontWeight: 600 },
    },
    axis: { x: { title: { text: 'Avg duration (ms)' } } },
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
    label: { text: 'count', position: 'right', style: { fontSize: 12, fontWeight: 600 } },
    axis: { x: { title: { text: 'Times requested' } } },
    legend: false,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Section */}
      <Row gutter={[20, 20]}>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Total Orchestrated"
            value={stats?.total ?? 0}
            loading={isLoading}
            footer={
              <Space>
                <Text type="secondary">Daily Tasks</Text>
                <Text strong>{Math.floor((stats?.total ?? 0) / 30)}</Text>
              </Space>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Success Rate"
            value={stats?.successRate ?? 0}
            suffix="%"
            loading={isLoading}
            footer={
              <Space>
                <Text type="secondary">Failed total</Text>
                <Text strong>{stats?.byStatus.FAILED ?? 0}</Text>
              </Space>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Average Latency"
            value={formatMs(stats?.avgDurationMs ?? 0)}
            loading={isLoading}
            footer={
              <Space>
                <Text type="secondary">P95 Latency</Text>
                <Text strong>{formatMs(stats?.p95DurationMs ?? 0)}</Text>
              </Space>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Active Jobs"
            value={(stats?.byStatus.PENDING ?? 0) + (stats?.byStatus.RUNNING ?? 0)}
            loading={isLoading}
            footer={
              <Space>
                <Text type="secondary">In queue</Text>
                <Text strong>{stats?.byStatus.PENDING ?? 0}</Text>
              </Space>
            }
          />
        </Col>
      </Row>

      {/* Main Charts */}
      <Card variant="borderless" styles={{ body: { padding: '0 24px 24px' } }}>
        <Tabs
          defaultActiveKey="1"
          size="large"
          tabBarStyle={{ marginBottom: 24 }}
          items={[
            {
              key: '1',
              label: 'Task Volume',
              children: (
                <Row gutter={48}>
                  <Col span={16}>
                    <Title level={5} style={{ marginBottom: 20 }}>Throughput (7 Days)</Title>
                    {isLoading ? <Spin /> : <Column {...timeSeriesConfig} height={300} />}
                  </Col>
                  <Col span={8}>
                    <Title level={5} style={{ marginBottom: 20 }}>Status Distribution</Title>
                    {isLoading ? <Spin /> : <Pie {...pieConfig} height={300} />}
                  </Col>
                </Row>
              ),
            },
            {
              key: '2',
              label: 'Performance Analysis',
              children: (
                <Row gutter={48}>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20 }}>Latency by Input Type</Title>
                    {isLoading ? <Spin /> : <Bar {...durationConfig} height={300} />}
                  </Col>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20 }}>Most Requested Outputs</Title>
                    {isLoading ? <Spin /> : <Bar {...outputUsageConfig} height={300} />}
                  </Col>
                </Row>
              ),
            },
          ]}
        />
      </Card>

      {/* Recent tasks Table */}
      <Card
        title={<Text strong>Recent Pipeline Activity</Text>}
        variant="borderless"
        extra={<Button type="link" onClick={() => navigate('/tasks')}>All Tasks</Button>}
      >
        <Table
          dataSource={stats?.recentTasks ?? []}
          columns={RECENT_COLS}
          rowKey="id"
          pagination={false}
          loading={isLoading}
          onRow={(record) => ({ 
            onClick: () => navigate(`/tasks/${record.id}`), 
            style: { cursor: 'pointer' } 
          })}
        />
      </Card>
    </div>
  )
}
