import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Table, Tag, Space, Typography, Spin, Alert, Button, Divider, Tooltip, Tabs, theme,
} from 'antd'
import {
  InfoCircleOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import {
  Pie, Column, Bar, Area, type PieConfig, type ColumnConfig, type BarConfig, type AreaConfig,
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

const RECENT_COLS = (token: any): ColumnsType<Task> => [
  {
    title: 'TASK ID',
    dataIndex: 'id',
    width: 100,
    render: (v: string) => <Text style={{ fontSize: 13, color: token.colorPrimary, fontWeight: 500 }}>{v.slice(0, 8).toUpperCase()}</Text>,
  },
  {
    title: 'TYPE',
    dataIndex: 'input_type',
    width: 100,
    render: (v: string) => (
      <Tag color="blue" variant="filled" style={{ fontSize: 11, fontWeight: 500 }}>
        {v.toUpperCase()}
      </Tag>
    ),
  },
  {
    title: 'CONTENT PREVIEW',
    dataIndex: 'input_data',
    ellipsis: true,
    render: (v: Record<string, unknown>) => (
      <Text style={{ fontSize: 13, color: token.colorTextSecondary }}>{inputPreview(v)}</Text>
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
        ? <Text style={{ fontSize: 12, color: token.colorText }}>{formatDuration(record.created_at, record.updated_at)}</Text>
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
    render: (v: string) => <Text style={{ fontSize: 12, color: token.colorTextDescription }}>{formatRelativeTime(v)}</Text>,
  },
]

export function DashboardPage() {
  const { data: stats, isLoading, error } = useDashboardStats()
  const navigate = useNavigate()
  const { token } = theme.useToken()

  if (error) return <Alert type="error" message={error.message} />

  const pieConfig: PieConfig = {
    data: stats ? Object.entries(stats.byStatus).filter(([, v]) => v > 0).map(([status, value]) => ({ status, value })) : [],
    angleField: 'value',
    colorField: 'status',
    radius: 0.8,
    innerRadius: 0.6,
    label: { text: 'value', style: { fontSize: 11, fontWeight: 600, fill: token.colorText } },
    legend: { color: { position: 'bottom', layout: { justifyContent: 'center' } } },
    scale: { color: { range: Object.values(STATUS_PIE_COLORS) } },
    annotations: stats ? [{
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
    }, {
      type: 'text',
      style: {
        text: 'Total Tasks',
        x: '50%',
        y: '62%',
        textAlign: 'center',
        fontSize: 14,
        fill: token.colorTextSecondary,
      },
    }] : [],
  }

  const dailyThroughputConfig: ColumnConfig = {
    data: stats?.timeSeriesLast7d ?? [],
    xField: 'date',
    yField: 'count',
    colorField: 'status',
    stack: true,
    scale: { color: { range: Object.values(STATUS_PIE_COLORS) } },
    axis: { 
      x: { label: { autoRotate: true, style: { fill: token.colorTextSecondary } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: { color: { position: 'top', layout: { justifyContent: 'flex-end' } } },
  }

  const hourlyVolumeConfig: ColumnConfig = {
    data: stats?.hourlyVolume24h ?? [],
    xField: 'hour',
    yField: 'count',
    colorField: 'status',
    stack: true,
    scale: { color: { range: Object.values(STATUS_PIE_COLORS) } },
    axis: { 
      x: { label: { style: { fill: token.colorTextSecondary, fontSize: 10 } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: false,
  }

  const concurrencyConfig: AreaConfig = {
    data: stats?.concurrencyPeak24h ?? [],
    xField: 'time',
    yField: 'count',
    smooth: true,
    color: token.colorPrimary,
    areaStyle: { fill: `l(270) 0:#ffffff 0.5:${token.colorPrimary} 1:${token.colorPrimary}` },
    axis: { 
      x: { label: { style: { fill: token.colorTextSecondary, fontSize: 10 } } },
      y: { title: { text: 'Active Tasks', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } }
    },
  }

  const successRateConfig: BarConfig = {
    data: stats?.inputSuccessRate ?? [],
    xField: 'rate',
    yField: 'type',
    colorField: 'type',
    label: {
      text: (d: any) => `${d.rate}%`,
      position: 'right',
      style: { fill: token.colorTextSecondary, fontWeight: 600 }
    },
    axis: { 
      x: { min: 0, max: 100, title: { text: 'Success Rate (%)', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: false,
  }

  const durationConfig: BarConfig = {
    data: stats?.durationByInputType ?? [],
    xField: 'avgMs',
    yField: 'type',
    colorField: 'type',
    label: {
      text: (d: any) => formatMs(d.avgMs),
      position: 'right',
      style: { fill: token.colorTextSecondary, fontWeight: 600 },
    },
    axis: { 
      x: { title: { text: 'Avg Duration', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: false,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Metrics Row */}
      <Row gutter={[20, 20]}>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Aggregated Orchestrations"
            value={stats?.total ?? 0}
            loading={isLoading}
            footer={<Space><Text type="secondary">System Capacity:</Text><Text strong style={{ color: token.colorTextHeading }}>99.9%</Text></Space>}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Global Success Rate"
            value={stats?.successRate ?? 0}
            suffix="%"
            loading={isLoading}
            footer={<Space><Text type="secondary">Failed Jobs:</Text><Text strong style={{ color: token.colorError }}>{stats?.byStatus.FAILED ?? 0}</Text></Space>}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Mean Pipeline Latency"
            value={formatMs(stats?.avgDurationMs ?? 0)}
            loading={isLoading}
            footer={<Space><Text type="secondary">P95 Tail:</Text><Text strong style={{ color: token.colorTextHeading }}>{formatMs(stats?.p95DurationMs ?? 0)}</Text></Space>}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="Concurrent Workload"
            value={(stats?.byStatus.PENDING ?? 0) + (stats?.byStatus.RUNNING ?? 0)}
            loading={isLoading}
            footer={<Space><Text type="secondary">Pending Queue:</Text><Text strong style={{ color: token.colorWarning }}>{stats?.byStatus.PENDING ?? 0}</Text></Space>}
          />
        </Col>
      </Row>

      {/* Analytics Tabs */}
      <Card variant="borderless" styles={{ body: { padding: '8px 24px 24px' } }}>
        <Tabs
          defaultActiveKey="1"
          size="large"
          items={[
            {
              key: '1',
              label: <Space><HistoryOutlined /> Volume & Trends</Space>,
              children: (
                <Row gutter={[40, 24]}>
                  <Col span={16}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Throughput Analysis (7 Days)</Title>
                    {isLoading ? <Spin /> : <Column {...dailyThroughputConfig} height={350} />}
                  </Col>
                  <Col span={8}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>State Distribution</Title>
                    {isLoading ? <Spin /> : <Pie {...pieConfig} height={350} />}
                  </Col>
                </Row>
              ),
            },
            {
              key: '2',
              label: <Space><AreaChartOutlined /> Temporal Analysis</Space>,
              children: (
                <Row gutter={[40, 24]}>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Hourly Throughput (24h)</Title>
                    {isLoading ? <Spin /> : <Column {...hourlyVolumeConfig} height={300} />}
                  </Col>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>System Load (Concurrency)</Title>
                    {isLoading ? <Spin /> : <Area {...concurrencyConfig} height={300} />}
                  </Col>
                </Row>
              ),
            },
            {
              key: '3',
              label: <Space><ThunderboltOutlined /> Performance Analysis</Space>,
              children: (
                <Row gutter={[40, 24]}>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Latency by Input Channel</Title>
                    {isLoading ? <Spin /> : <Bar {...durationConfig} height={300} />}
                  </Col>
                  <Col span={12}>
                    <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Reliability by Input Type</Title>
                    {isLoading ? <Spin /> : <Bar {...successRateConfig} height={300} />}
                  </Col>
                </Row>
              ),
            },
          ]}
        />
      </Card>

      {/* Recent Activity */}
      <Card
        title={<Space><BarChartOutlined /> <Text strong style={{ color: token.colorTextHeading }}>Recent Pipeline Activity</Text></Space>}
        variant="borderless"
        extra={<Button type="link" onClick={() => navigate('/tasks')}>Explore full history →</Button>}
      >
        <Table
          dataSource={stats?.recentTasks ?? []}
          columns={RECENT_COLS(token)}
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
