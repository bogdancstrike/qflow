import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Table, Tag, Space, Typography, Spin, Alert, Button, Divider, Tooltip, Tabs, theme, Segmented, Progress, Statistic,
} from 'antd'
import {
  InfoCircleOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
  RiseOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
  ExperimentOutlined,
  DeploymentUnitOutlined,
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
  title, value, suffix, loading, footer, icon, tooltip,
}: {
  title: string
  value: string | number
  suffix?: string
  loading?: boolean
  footer?: React.ReactNode
  icon?: React.ReactNode
  tooltip?: string
}) {
  const { token } = theme.useToken()
  return (
    <Card variant="borderless" loading={loading} styles={{ body: { padding: '20px 24px 8px' } }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Space size={8}>
          {icon}
          <Text style={{ fontSize: 13, color: token.colorTextSecondary }}>{title}</Text>
        </Space>
        {tooltip && (
          <Tooltip title={tooltip}>
            <InfoCircleOutlined style={{ color: token.colorTextDescription, cursor: 'help' }} />
          </Tooltip>
        )}
      </div>
      <div style={{ margin: '4px 0 12px' }}>
        <Text style={{ fontSize: 26, color: token.colorTextHeading, fontWeight: 600 }}>
          {typeof value === 'number' ? value.toLocaleString() : value}{suffix}
        </Text>
      </div>
      <Divider style={{ margin: '8px 0' }} />
      <div style={{ padding: '4px 0 8px', fontSize: 13, color: token.colorTextSecondary }}>
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
  const [volumeGranularity, setVolumeGranularity] = useState<'min' | 'hour' | 'day' | 'week'>('day')
  const [temporalGranularity, setTemporalGranularity] = useState<'min' | 'hour'>('hour')

  const volumeData = useMemo(() => {
    if (!stats) return []
    if (volumeGranularity === 'min') return stats.minutely_volume_1h || []
    if (volumeGranularity === 'hour') return stats.hourly_volume_24h || []
    if (volumeGranularity === 'week') return stats.weekly_volume_12w || []
    return stats.daily_volume_30d || []
  }, [stats, volumeGranularity])

  const temporalData = useMemo(() => {
    if (!stats) return []
    return temporalGranularity === 'min' ? (stats.concurrency_1h || []) : (stats.concurrency_24h || [])
  }, [stats, temporalGranularity])

  const pieConfig: PieConfig = {
    data: (stats && stats.byStatus) ? Object.entries(stats.byStatus).filter(([, v]) => v > 0).map(([status, value]) => ({ status, value })) : [],
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
        text: `${(stats.total || 0).toLocaleString()}`,
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
        text: 'Total Jobs',
        x: '50%',
        y: '62%',
        textAlign: 'center',
        fontSize: 14,
        fill: token.colorTextSecondary,
      },
    }] : [],
  }

  const volumeConfig: ColumnConfig = {
    data: volumeData,
    xField: 'time',
    yField: 'count',
    colorField: 'status',
    stack: true,
    scale: { color: { range: Object.values(STATUS_PIE_COLORS) } },
    axis: { 
      x: { label: { autoRotate: true, style: { fill: token.colorTextSecondary, fontSize: 10 } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: { color: { position: 'top', layout: { justifyContent: 'flex-end' } } },
  }

  const concurrencyConfig: AreaConfig = {
    data: temporalData,
    xField: 'time',
    yField: 'count',
    style: {
      fill: token.colorPrimary,
      fillOpacity: 0.2,
    },
    line: {
      style: {
        stroke: token.colorPrimary,
        lineWidth: 2,
      },
    },
    axis: { 
      x: { label: { style: { fill: token.colorTextSecondary, fontSize: 10 }, autoRotate: true } },
      y: { title: { text: 'Active Tasks', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } }
    },
  }

  const queueLatencyConfig: AreaConfig = {
    data: stats?.queue_latency_24h ?? [],
    xField: 'time',
    yField: 'avgMs',
    style: {
      fill: token.colorWarning,
      fillOpacity: 0.1,
    },
    line: {
      style: {
        stroke: token.colorWarning,
        lineWidth: 2,
      },
    },
    axis: { 
      x: { label: { style: { fill: token.colorTextSecondary, fontSize: 10 }, autoRotate: true } },
      y: { title: { text: 'Wait Time (ms)', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } }
    },
  }

  const outputRequestedConfig: BarConfig = {
    data: (stats && stats.byOutputRequested) ? Object.entries(stats.byOutputRequested).map(([type, count]) => ({ type: OUTPUT_LABELS[type as OutputType] || type, count })) : [],
    xField: 'count',
    yField: 'type',
    colorField: 'type',
    label: {
      text: 'count',
      position: 'right',
      style: { fill: token.colorTextSecondary, fontWeight: 600 },
    },
    axis: { 
      x: { title: { text: 'Request Volume', style: { fill: token.colorTextSecondary } }, label: { style: { fill: token.colorTextSecondary } } },
      y: { label: { style: { fill: token.colorTextSecondary } } }
    },
    legend: false,
  }

  const inputChannelConfig: PieConfig = {
    data: (stats && stats.byInputType) ? Object.entries(stats.byInputType).map(([type, value]) => ({ type: type.toUpperCase(), value })) : [],
    angleField: 'value',
    colorField: 'type',
    radius: 0.7,
    label: { text: 'value', style: { fontSize: 10, fill: token.colorText } },
    legend: { color: { position: 'bottom' } },
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Backend Status Alert (only if error) */}
      {error && (
        <Alert 
          type="warning" 
          message="Analytics engine is currently unavailable. Displaying cached or empty data." 
          showIcon 
          action={<Button size="small" onClick={() => window.location.reload()}>Retry</Button>}
        />
      )}

      {/* Real-time Velocity Card */}
      <Card variant="borderless" styles={{ body: { padding: '12px 24px' } }}>
        <Row gutter={48} align="middle">
          <Col>
            <Space direction="vertical" size={0}>
              <Space size={4}>
                <Text type="secondary" style={{ fontSize: 11 }}>CURRENT VELOCITY</Text>
                <Tooltip title="Tasks Per Minute (TPM): Number of new tasks submitted in the last 60 seconds.">
                  <InfoCircleOutlined style={{ fontSize: 10, color: token.colorTextDescription }} />
                </Tooltip>
              </Space>
              <Space align="baseline">
                <Text style={{ fontSize: 28, fontWeight: 700 }}>{stats?.tpm_current ?? 0}</Text>
                <Text type="secondary">TPM</Text>
                <Tag color="success" icon={<RiseOutlined />} style={{ borderRadius: 10, marginLeft: 8 }}>
                  REAL-TIME
                </Tag>
              </Space>
            </Space>
          </Col>
          <Divider orientation="vertical" style={{ height: 40 }} />
          <Col>
            <Space direction="vertical" size={0}>
              <Space size={4}>
                <Text type="secondary" style={{ fontSize: 11 }}>15M AVG VELOCITY</Text>
                <Tooltip title="Average Tasks Per Minute over the last 15 minutes.">
                  <InfoCircleOutlined style={{ fontSize: 10, color: token.colorTextDescription }} />
                </Tooltip>
              </Space>
              <Space align="baseline">
                <Text style={{ fontSize: 24, fontWeight: 600 }}>{stats?.tpm_avg_15m ?? 0}</Text>
                <Text type="secondary">TPM</Text>
              </Space>
            </Space>
          </Col>
          <Col flex="auto" style={{ textAlign: 'right' }}>
             <Space size={24}>
               <Statistic title="Total Ingested" value={stats?.total || 0} groupSeparator="," />
               <Statistic 
                 title="Success Rate" 
                 value={stats?.successRate || 0} 
                 suffix="%" 
                 precision={1} 
                 styles={{ content: { color: token.colorSuccess } }} 
               />
             </Space>
          </Col>
        </Row>
      </Card>

      {/* Main Metrics Row */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="ACTIVE TASKS"
            value={stats?.byStatus?.RUNNING ?? 0}
            loading={isLoading}
            icon={<PlayCircleOutlined style={{ color: token.colorInfo }} />}
            tooltip="Number of tasks currently being executed by the workers."
            footer={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">Processing now</Text>
                <Text strong style={{ color: token.colorInfo }}>{((stats?.byStatus?.RUNNING ?? 0) / (stats?.total || 1) * 100).toFixed(1)}%</Text>
              </div>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="PENDING QUEUE"
            value={stats?.byStatus?.PENDING ?? 0}
            loading={isLoading}
            icon={<ClockCircleOutlined style={{ color: token.colorWarning }} />}
            tooltip="Tasks waiting in Kafka/Redis to be picked up by a worker."
            footer={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">Wait: {formatMs(stats?.avgQueueMs ?? 0)}</Text>
                <Text strong style={{ color: token.colorWarning }}>{((stats?.byStatus?.PENDING ?? 0) / (stats?.total || 1) * 100).toFixed(1)}%</Text>
              </div>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="COMPLETED"
            value={stats?.byStatus?.COMPLETED ?? 0}
            loading={isLoading}
            icon={<CheckCircleOutlined style={{ color: token.colorSuccess }} />}
            tooltip="Successfully finished workflows."
            footer={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">Finalized jobs</Text>
                <Text strong style={{ color: token.colorSuccess }}>{((stats?.byStatus?.COMPLETED ?? 0) / (stats?.total || 1) * 100).toFixed(1)}%</Text>
              </div>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <AnalysisCard
            title="FAILED"
            value={stats?.byStatus?.FAILED ?? 0}
            loading={isLoading}
            icon={<AlertOutlined style={{ color: token.colorError }} />}
            tooltip="Tasks that encountered a terminal error or were aborted."
            footer={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">Error rate</Text>
                <Text strong style={{ color: token.colorError }}>{((stats?.byStatus?.FAILED ?? 0) / (stats?.total || 1) * 100).toFixed(1)}%</Text>
              </div>
            }
          />
        </Col>
      </Row>

      {/* Latency & Processing Row */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <AnalysisCard
            title="AVG QUEUE LATENCY"
            value={formatMs(stats?.avgQueueMs ?? 0)}
            loading={isLoading}
            icon={<HistoryOutlined style={{ color: token.colorWarning }} />}
            tooltip="Average time a task spends in PENDING state before a worker starts execution."
            footer={<Text type="secondary">Time from enqueue to pick-up</Text>}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <AnalysisCard
            title="AVG PROCESSING SPEED"
            value={formatMs(stats?.avgProcessingMs ?? 0)}
            loading={isLoading}
            icon={<ThunderboltOutlined style={{ color: token.colorInfo }} />}
            tooltip="Average time spent in RUNNING state (actual DAG execution time)."
            footer={<Text type="secondary">Execution time per individual task</Text>}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <AnalysisCard
            title="AVG END-TO-END"
            value={formatMs(stats?.avgDurationMs ?? 0)}
            loading={isLoading}
            icon={<RiseOutlined style={{ color: token.colorPrimary }} />}
            tooltip="Total time from task creation to completion (Queue + Processing)."
            footer={<Text type="secondary">Total lifecycle duration</Text>}
          />
        </Col>
      </Row>

      {/* Analytics Tabs */}
      <Card variant="borderless" styles={{ body: { padding: '16px 24px 24px' } }}>
        <Tabs
          defaultActiveKey="1"
          size="large"
          items={[
            {
              key: '1',
              label: <Space><HistoryOutlined /> Throughput & Distribution</Space>,
              children: (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <Title level={5} style={{ margin: 0, color: token.colorTextHeading }}>Pipeline Volume</Title>
                    <Segmented
                      value={volumeGranularity}
                      onChange={(v) => setVolumeGranularity(v as any)}
                      options={[
                        { label: 'Minutes', value: 'min' },
                        { label: 'Hourly', value: 'hour' },
                        { label: 'Daily', value: 'day' },
                        { label: 'Weekly', value: 'week' },
                      ]}
                    />
                  </div>
                  <Row gutter={[40, 24]}>
                    <Col span={16}>
                      {isLoading ? <Spin /> : <Column {...volumeConfig} height={350} />}
                    </Col>
                    <Col span={8}>
                      <Title level={5} style={{ marginBottom: 20, textAlign: 'center', color: token.colorTextHeading }}>Status Split</Title>
                      {isLoading ? <Spin /> : <Pie {...pieConfig} height={350} />}
                    </Col>
                  </Row>
                </div>
              ),
            },
            {
              key: '2',
              label: <Space><AreaChartOutlined /> Latency & Concurrency</Space>,
              children: (
                <div style={{ marginTop: 16 }}>
                   <Row gutter={[40, 24]}>
                    <Col span={12}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                        <Title level={5} style={{ margin: 0, color: token.colorTextHeading }}>System Load (Concurrency)</Title>
                        <Segmented
                          size="small"
                          value={temporalGranularity}
                          onChange={(v) => setTemporalGranularity(v as any)}
                          options={[
                            { label: '60m', value: 'min' },
                            { label: '24h', value: 'hour' },
                          ]}
                        />
                      </div>
                      {isLoading ? <Spin /> : <Area {...concurrencyConfig} height={300} />}
                    </Col>
                    <Col span={12}>
                      <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Queue Latency Trend (24h)</Title>
                      {isLoading ? <Spin /> : <Area {...queueLatencyConfig} height={300} />}
                    </Col>
                  </Row>
                </div>
              ),
            },
            {
              key: '3',
              label: <Space><DeploymentUnitOutlined /> Flow & Output Analytics</Space>,
              children: (
                <div style={{ marginTop: 16 }}>
                  <Row gutter={[40, 24]}>
                    <Col span={14}>
                      <Title level={5} style={{ marginBottom: 20, color: token.colorTextHeading }}>Popular Analysis Types (Requested Outputs)</Title>
                      {isLoading ? <Spin /> : <Bar {...outputRequestedConfig} height={350} />}
                    </Col>
                    <Col span={10}>
                      <Title level={5} style={{ marginBottom: 20, textAlign: 'center', color: token.colorTextHeading }}>Input Channel Distribution</Title>
                      {isLoading ? <Spin /> : <Pie {...inputChannelConfig} height={350} />}
                    </Col>
                  </Row>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* Recent Activity */}
      <Card
        title={<Space><ExperimentOutlined /> <Text strong style={{ color: token.colorTextHeading }}>Recent Activity Stream</Text></Space>}
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
