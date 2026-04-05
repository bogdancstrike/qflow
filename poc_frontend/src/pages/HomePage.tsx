import { useQuery } from '@tanstack/react-query'
import { Row, Col, Typography, Space, Spin } from 'antd'
import { tasksApi } from '@/api/tasks'
import { TaskForm } from '@/components/task/TaskForm'
import { TaskCard } from '@/components/task/TaskCard'
import { EmptyState } from '@/components/shared/EmptyState'
import type { TaskListResponse } from '@/types'

const { Title, Text } = Typography

export function HomePage() {
  const { data, isLoading } = useQuery<TaskListResponse, Error>({
    queryKey: ['tasks', 'recent'],
    queryFn: () => tasksApi.list({ limit: 10, sort: 'created_at:desc' }),
    refetchInterval: 3000,
  })

  return (
    <Row gutter={24}>
      <Col xs={24} lg={12}>
        <Title level={4} style={{ marginTop: 0 }}>Submit a Task</Title>
        <TaskForm />
      </Col>

      <Col xs={24} lg={12}>
        <Space style={{ justifyContent: 'space-between', width: '100%', marginBottom: 8 }}>
          <Title level={4} style={{ marginTop: 0 }}>Recent Tasks</Title>
          {isLoading && <Spin size="small" />}
        </Space>

        {data?.tasks.length === 0 && !isLoading && (
          <EmptyState description="No tasks yet — submit one to get started" />
        )}

        {data?.tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </Col>
    </Row>
  )
}
