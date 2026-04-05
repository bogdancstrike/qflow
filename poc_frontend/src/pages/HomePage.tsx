import { useQuery } from '@tanstack/react-query'
import { Row, Col, Typography, Space, Spin, Card, Divider } from 'antd'
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
  const { data, isLoading } = useQuery<TaskListResponse, Error>({
    queryKey: ['tasks', 'recent'],
    queryFn: () => tasksApi.list({ limit: 4, sort: 'created_at:desc' }),
    refetchInterval: 5000,
  })

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, fontWeight: 600 }}>Orchestrator Workspace</Title>
        <Text type="secondary" style={{ fontSize: 16 }}>
          Configure and initialize your AI processing pipeline.
        </Text>
      </div>

      <Row gutter={[24, 24]}>
        {/* Main Form Column */}
        <Col xs={24} lg={16}>
          <Card 
            bordered={false} 
            bodyStyle={{ padding: '32px 40px' }}
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
              bordered={false} 
              title={<Space><BulbOutlined style={{ color: '#faad14' }} /> <Text strong>System Tips</Text></Space>}
              bodyStyle={{ padding: '16px 20px' }}
            >
              <ul style={{ paddingLeft: 20, margin: 0, color: '#595959', fontSize: 13, lineHeight: '24px' }}>
                <li>YouTube links are auto-downloaded and transcribed.</li>
                <li>Parallel branches speed up multi-output analysis.</li>
                <li>English translation is automatic for NER and Sentiment.</li>
                <li>Check the <b>Flow Catalogue</b> for detailed node info.</li>
              </ul>
            </Card>

            {/* Recent Tasks */}
            <Card 
              bordered={false} 
              title={<Space><HistoryOutlined /> <Text strong>Recent Activity</Text></Space>}
              bodyStyle={{ padding: '12px 16px' }}
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
