import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Space, Typography, Descriptions, Button, Popconfirm, Alert, Collapse,
  Tag, Spin, Result, Skeleton,
} from 'antd'
import { DeleteOutlined, ReloadOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { tasksApi } from '@/api/tasks'
import { useTaskPolling } from '@/hooks/useTaskPolling'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { CopyButton } from '@/components/shared/CopyButton'
import { OutputViewer } from '@/components/task/OutputViewer'
import { DagGraph } from '@/components/dag/DagGraph'
import { StepLogTable } from '@/components/logs/StepLogTable'
import { OUTPUT_LABELS } from '@/lib/constants'
import { formatRelativeTime, formatDuration, inputPreview } from '@/lib/formatters'

const { Title, Text } = Typography

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showLogs, setShowLogs] = useState(false)

  const { data: task, isLoading, error, refetch } = useTaskPolling(id!)

  const { mutate: del, isPending: deleting } = useMutation({
    mutationFn: () => tasksApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      navigate('/tasks')
    },
  })

  if (isLoading) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error) return <Result status="error" title="Failed to load task" subTitle={error.message} />
  if (!task) return <Result status="404" title="Task not found" />

  const sourceText =
    typeof task.input_data?.text === 'string' ? (task.input_data.text as string) : undefined

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      {/* Header */}
      <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
        <Space>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/tasks')}>
            Back
          </Button>
          <Title level={4} style={{ margin: 0 }}>Task Detail</Title>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()} />
          <Popconfirm
            title="Delete this task and all its logs?"
            onConfirm={() => del()}
            okText="Delete"
            okType="danger"
          >
            <Button danger icon={<DeleteOutlined />} loading={deleting}>Delete</Button>
          </Popconfirm>
        </Space>
      </Space>

      {/* Meta */}
      <div style={{ background: '#fff', borderRadius: 8, padding: 16, border: '1px solid #f0f0f0' }}>
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="Task ID">
            <Space>
              <Text code style={{ fontSize: 12 }}>{task.id}</Text>
              <CopyButton text={task.id} />
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <TaskStatusBadge status={task.status} showDot />
          </Descriptions.Item>
          <Descriptions.Item label="Input type">
            <Tag>{task.input_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Input">
            <Text type="secondary">{inputPreview(task.input_data as Record<string, unknown>)}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Outputs">
            <Space wrap>
              {task.outputs.map((o) => <Tag key={o}>{OUTPUT_LABELS[o]}</Tag>)}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Retry count">
            {task.retry_count}
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {formatRelativeTime(task.created_at)}
          </Descriptions.Item>
          <Descriptions.Item label="Duration">
            {task.status === 'COMPLETED' || task.status === 'FAILED'
              ? formatDuration(task.created_at, task.updated_at)
              : '—'}
          </Descriptions.Item>
          {task.current_step && (
            <Descriptions.Item label="Current step">
              <Tag color="blue">{task.current_step}</Tag>
            </Descriptions.Item>
          )}
        </Descriptions>

        {task.error && (
          <Alert
            type="error"
            message="Task failed"
            description={<pre style={{ fontSize: 12, margin: 0 }}>{JSON.stringify(task.error, null, 2)}</pre>}
            style={{ marginTop: 12 }}
          />
        )}
      </div>

      {/* DAG */}
      <div style={{ background: '#fff', borderRadius: 8, padding: 16, border: '1px solid #f0f0f0' }}>
        <Title level={5} style={{ margin: '0 0 12px' }}>Execution Plan</Title>
        <DagGraph
          plan={task.execution_plan}
          currentStep={task.current_step}
          stepResults={task.step_results}
          hasError={task.status === 'FAILED'}
        />
      </div>

      {/* Results */}
      {task.status === 'COMPLETED' && task.final_output && (
        <div>
          <Title level={5} style={{ marginBottom: 12 }}>Results</Title>
          <OutputViewer finalOutput={task.final_output} sourceText={sourceText} />
        </div>
      )}

      {(task.status === 'PENDING' || task.status === 'RUNNING') && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">Processing… checking every 2s</Text>
          </div>
        </div>
      )}

      {/* Logs */}
      <Collapse
        ghost
        onChange={(keys) => setShowLogs(keys.includes('logs'))}
        items={[{
          key: 'logs',
          label: 'Step execution logs',
          children: showLogs ? <StepLogTable taskId={task.id} /> : null,
        }]}
      />
    </Space>
  )
}
