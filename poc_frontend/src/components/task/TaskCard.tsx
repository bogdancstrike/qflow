import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, Space, Typography, Tag, Button, Popconfirm, Tooltip } from 'antd'
import {
  FileTextOutlined,
  YoutubeOutlined,
  FileOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import type { Task } from '@/types'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { OUTPUT_LABELS } from '@/lib/constants'
import { formatRelativeTime, formatDuration, inputPreview } from '@/lib/formatters'
import { tasksApi } from '@/api/tasks'

const { Text } = Typography

const INPUT_ICON = {
  text: <FileTextOutlined />,
  youtube_url: <YoutubeOutlined style={{ color: '#ff0000' }} />,
  audio_path: <FileOutlined />,
}

interface Props {
  task: Task
}

export function TaskCard({ task }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { mutate: del } = useMutation({
    mutationFn: () => tasksApi.delete(task.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const duration =
    task.status === 'COMPLETED' || task.status === 'FAILED'
      ? formatDuration(task.created_at, task.updated_at)
      : null

  return (
    <Card
      size="small"
      hoverable
      onClick={() => navigate(`/tasks/${task.id}`)}
      style={{ marginBottom: 8 }}
      bodyStyle={{ padding: '10px 16px' }}
    >
      <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
        <Space>
          {INPUT_ICON[task.input_type]}
          <Text code style={{ fontSize: 12 }}>
            {task.id.slice(0, 8)}
          </Text>
          <Text type="secondary" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {inputPreview(task.input_data as Record<string, unknown>)}
          </Text>
        </Space>

        <Space onClick={(e) => e.stopPropagation()}>
          <TaskStatusBadge status={task.status} showDot />
          {duration && <Text type="secondary" style={{ fontSize: 12 }}>{duration}</Text>}
          <Text type="secondary" style={{ fontSize: 12 }}>{formatRelativeTime(task.created_at)}</Text>

          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}`) }}
          />
          <Popconfirm
            title="Delete this task?"
            onConfirm={(e) => { e?.stopPropagation(); del() }}
            okText="Delete"
            okType="danger"
          >
            <Button size="small" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()} />
          </Popconfirm>
        </Space>
      </Space>

      <Space style={{ marginTop: 6 }} wrap>
        {task.outputs.map((o) => (
          <Tag key={o} style={{ fontSize: 11 }}>{OUTPUT_LABELS[o]}</Tag>
        ))}
      </Space>
    </Card>
  )
}
