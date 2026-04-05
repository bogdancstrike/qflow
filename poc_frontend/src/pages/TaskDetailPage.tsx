import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Space, Typography, Descriptions, Button, Popconfirm, Alert, Collapse,
  Tag, Spin, Result, Skeleton, Card, theme,
} from 'antd'
import { DeleteOutlined, ReloadOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { tasksApi } from '@/api/tasks'
import { useTaskPolling } from '@/hooks/useTaskPolling'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { CopyButton } from '@/components/shared/CopyButton'
import { OutputViewer } from '@/components/task/OutputViewer'
import { DagGraph } from '@/components/dag/DagGraph'
import { StepLogTable } from '@/components/logs/StepLogTable'
import { formatRelativeTime, formatDuration, inputPreview } from '@/lib/formatters'

const { Title, Text } = Typography

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showLogs, setShowLogs] = useState(false)
  const { token } = theme.useToken()

  const { data: task, isLoading, error, refetch } = useTaskPolling(id!)

  const { mutate: del, isPending: deleting } = useMutation({
    mutationFn: () => tasksApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      navigate('/tasks')
    },
  })

  if (isLoading) return <div style={{ padding: 40 }}><Skeleton active paragraph={{ rows: 12 }} /></div>
  if (error) return <Result status="error" title="Failed to load task" subTitle={error.message} />
  if (!task) return <Result status="404" title="Task not found" />

  const sourceText =
    typeof task.input_data?.text === 'string' ? (task.input_data.text as string) : undefined

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={24}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space size={16}>
          <Button 
            icon={<ArrowLeftOutlined />} 
            type="text" 
            onClick={() => navigate(-1)}
            style={{ color: token.colorTextSecondary }}
          >
            Back
          </Button>
          <div>
            <Title level={3} style={{ margin: 0, letterSpacing: '-0.025em', color: token.colorTextHeading }}>
              Task <Text code style={{ fontSize: 20 }}>{task.id.slice(0, 8).toUpperCase()}</Text>
            </Title>
            <Text style={{ fontSize: 13, color: token.colorTextSecondary }}>
              Detailed execution status and results.
            </Text>
          </div>
        </Space>
        <Space size={12}>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()} />
          <Popconfirm
            title="Delete this task and all its logs?"
            onConfirm={() => del()}
            okText="Delete"
            okType="danger"
            placement="bottomRight"
          >
            <Button danger icon={<DeleteOutlined />} loading={deleting}>Delete Task</Button>
          </Popconfirm>
        </Space>
      </div>

      {/* Meta Card */}
      <Card variant="borderless" styles={{ body: { padding: 24 } }}>
        <Descriptions 
          column={{ xs: 1, sm: 2, md: 3 }} 
          size="middle" 
          labelStyle={{ color: token.colorTextSecondary, fontWeight: 500 }}
          contentStyle={{ color: token.colorTextHeading }}
        >
          <Descriptions.Item label="Status">
            <TaskStatusBadge status={task.status} showDot />
          </Descriptions.Item>
          <Descriptions.Item label="Input Type">
            <Tag color="blue" variant="filled" style={{ fontWeight: 600 }}>{task.input_type.toUpperCase()}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            <Text style={{ color: token.colorTextHeading }}>{formatRelativeTime(task.created_at)}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Duration">
            <Text strong style={{ color: token.colorTextHeading }}>
              {task.status === 'COMPLETED' || task.status === 'FAILED'
                ? formatDuration(task.created_at, task.updated_at)
                : '—'}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Retry Count">
            <Text style={{ color: token.colorTextHeading }}>{task.retry_count}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Full ID">
             <Space size={4}>
              <Text code style={{ fontSize: 11 }}>{task.id}</Text>
              <CopyButton text={task.id} />
            </Space>
          </Descriptions.Item>
        </Descriptions>
        
        <div style={{ marginTop: 24, paddingTop: 24, borderTop: `1px solid ${token.colorBorderSecondary}` }}>
           <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Text strong style={{ fontSize: 12, letterSpacing: '0.05em', color: token.colorTextSecondary }}>INPUT PREVIEW</Text>
              <div style={{ background: token.colorFillAlter, padding: '12px 16px', borderRadius: 8, border: `1px solid ${token.colorBorderSecondary}` }}>
                <Text style={{ fontSize: 14, color: token.colorText, lineHeight: 1.6 }}>
                  {inputPreview(task.input_data as Record<string, unknown>)}
                </Text>
              </div>
           </Space>
        </div>

        {task.error && (
          <Alert
            type="error"
            showIcon
            message="Execution Error"
            description={<pre style={{ fontSize: 12, margin: '8px 0 0' }}>{JSON.stringify(task.error, null, 2)}</pre>}
            style={{ marginTop: 20, borderRadius: 8 }}
          />
        )}
      </Card>

      {/* DAG */}
      <Card 
        variant="borderless"
        title={<Text strong style={{ fontSize: 14, color: token.colorTextHeading }}>Execution Plan & Real-time Progress</Text>}
      >
        <DagGraph
          plan={task.execution_plan}
          currentStep={task.current_step}
          stepResults={task.step_results}
          hasError={task.status === 'FAILED'}
        />
      </Card>

      {/* Results */}
      {task.status === 'COMPLETED' && task.final_output && (
        <div style={{ marginTop: 8 }}>
          <Title level={4} style={{ marginBottom: 16, letterSpacing: '-0.025em', color: token.colorTextHeading }}>Analytics Results</Title>
          <OutputViewer finalOutput={task.final_output} sourceText={sourceText} />
        </div>
      )}

      {(task.status === 'PENDING' || task.status === 'RUNNING') && (
        <Card variant="borderless" style={{ textAlign: 'center', padding: '48px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 20 }}>
            <Text strong style={{ fontSize: 16, display: 'block', color: token.colorTextHeading }}>Orchestrating AI Services...</Text>
            <Text style={{ color: token.colorTextSecondary }}>Status refreshes every 2 seconds.</Text>
          </div>
        </Card>
      )}

      {/* Logs */}
      <Card 
        variant="borderless"
        size="small" 
        style={{ marginTop: 8 }}
      >
        <Collapse
          ghost
          onChange={(keys) => setShowLogs(keys.includes('logs'))}
          items={[{
            key: 'logs',
            label: <Text strong style={{ color: token.colorTextSecondary }}>Technical Execution Logs</Text>,
            children: showLogs ? <StepLogTable taskId={task.id} /> : null,
          }]}
        />
      </Card>
    </Space>
  )
}
