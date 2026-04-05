import { useQuery } from '@tanstack/react-query'
import { Row, Col, Typography, Space, Spin, Card, theme } from 'antd'
import {
  RocketOutlined,
  HistoryOutlined,
  BulbOutlined,
} from '@ant-design/icons'
import { tasksApi } from '@/api/tasks'
import { TaskForm } from '@/components/task/TaskForm'
import { TaskCard } from '@/components/task/TaskCard'
import { EmptyState } from '@/components/shared/EmptyState'
import type { TaskListResponse } from '@/types'

const { Title, Text } = Typography

export function HomePage() {
  const { token } = theme.useToken()
  const { data, isLoading } = useQuery<TaskListResponse, Error>({
    queryKey: ['tasks', 'recent'],
    queryFn: () => tasksApi.list({ limit: 4, sort: 'created_at:desc' }),
    refetchInterval: 5000,
  })

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, fontWeight: 600, color: token.colorTextHeading }}>Orchestrator Workspace</Title>
        <Text style={{ fontSize: 16, color: token.colorTextSecondary }}>
          Configure and initialize your AI processing pipeline.
        </Text>
      </div>

      <Row gutter={[24, 24]}>
        {/* Main Form Column */}
        <Col xs={24} lg={16}>
          <Card 
            variant="borderless"
            styles={{ body: { padding: '32px 40px' } }}
            title={<Space><RocketOutlined /> <Text strong>Pipeline Configuration</Text></Space>}
          >
            <TaskForm />
          </Card>
        </Col>

        {/* Info & Recent Column */}
        <Col xs={24} lg={8}>
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            {/* Quick Tips */}
            <Card 
              variant="borderless"
              title={<Space><BulbOutlined style={{ color: '#faad14' }} /> <Text strong>System Tips</Text></Space>}
              styles={{ body: { padding: '16px 20px' } }}
            >
              <ul style={{ paddingLeft: 20, margin: 0, color: token.colorTextSecondary, fontSize: 13, lineHeight: '24px' }}>
                <li>YouTube links are auto-downloaded and transcribed.</li>
                <li>Parallel branches speed up multi-output analysis.</li>
                <li>English translation is automatic for NER and Sentiment.</li>
                <li>Check the <b>Flow Catalogue</b> for detailed node info.</li>
              </ul>
            </Card>

            {/* Recent Tasks */}
            <Card 
              variant="borderless"
              title={<Space><HistoryOutlined /> <Text strong>Recent Activity</Text></Space>}
              styles={{ body: { padding: '12px 16px' } }}
              extra={isLoading && <Spin size="small" />}
            >
              {data?.tasks.length === 0 && !isLoading && (
                <EmptyState description="No tasks yet" />
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {data?.tasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </div>
              
              {data?.tasks.length === 4 && (
                <div style={{ textAlign: 'center', marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>Latest 4 tasks shown</Text>
                </div>
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  )
}
