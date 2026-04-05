import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Space, Typography, Tag, Button, Popconfirm, Divider } from 'antd'
import {
  FileTextOutlined,
  YoutubeOutlined,
  FileOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { Task } from '@/types'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { formatRelativeTime, inputPreview } from '@/lib/formatters'
import { tasksApi } from '@/api/tasks'

const { Text } = Typography

const INPUT_ICON = {
  text: <FileTextOutlined style={{ color: '#1890ff' }} />,
  youtube_url: <YoutubeOutlined style={{ color: '#ff4d4f' }} />,
  audio_path: <FileOutlined style={{ color: '#52c41a' }} />,
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

  return (
    <div 
      onClick={() => navigate(`/tasks/${task.id}`)}
      style={{ 
        padding: '12px 0', 
        borderBottom: '1px solid #f0f0f0', 
        cursor: 'pointer',
        transition: 'background 0.2s',
      }}
      className="task-card-hover"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <Space size={8}>
          {INPUT_ICON[task.input_type]}
          <Text strong style={{ fontSize: 13 }}>{task.id.slice(0, 8).toUpperCase()}</Text>
        </Space>
        <TaskStatusBadge status={task.status} showDot={false} />
      </div>
      
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block' }} ellipsis>
          {inputPreview(task.input_data as Record<string, unknown>)}
        </Text>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={{ fontSize: 11, color: '#bfbfbf' }}>{formatRelativeTime(task.created_at)}</Text>
        <Popconfirm
          title="Delete task?"
          onConfirm={(e) => { e?.stopPropagation(); del() }}
          okText="Yes"
          cancelText="No"
        >
          <Button 
            size="small" 
            type="text" 
            danger 
            icon={<DeleteOutlined style={{ fontSize: 12 }} />} 
            onClick={(e) => e.stopPropagation()} 
          />
        </Popconfirm>
      </div>
    </div>
  )
}
