import { Typography, Table, Tag, Space, Badge, Skeleton, Alert, Card, Row, Col } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useFlows } from '@/hooks/useFlows'
import { DagGraph } from '@/components/dag/DagGraph'
import { NODE_LABELS, NODE_DESCRIPTIONS, OUTPUT_LABELS, OUTPUT_DESCRIPTIONS } from '@/lib/constants'
import type { NodeDef, OutputType, ExecutionPlan } from '@/types'

const { Title, Text } = Typography

// Build a "full topology" plan showing all 9 nodes for the static overview
const FULL_PLAN: ExecutionPlan = {
  input_type: 'youtube_url',
  ingest_steps: ['ytdlp_download', 'stt'],
  branches: [
    { output_type: 'ner_result', steps: ['lang_detect', 'translate', 'ner'] },
    { output_type: 'sentiment_result', steps: ['lang_detect', 'translate', 'sentiment'] },
    { output_type: 'summary', steps: ['summarize'] },
    { output_type: 'iptc_tags', steps: ['iptc'] },
    { output_type: 'keywords', steps: ['keyword_extract'] },
  ],
}

const COLUMNS: ColumnsType<NodeDef> = [
  {
    title: 'Node',
    dataIndex: 'node_id',
    render: (v) => <Text code>{v}</Text>,
  },
  {
    title: 'Label',
    dataIndex: 'node_id',
    render: (v) => NODE_LABELS[v] ?? v,
  },
  {
    title: 'Phase',
    dataIndex: 'phase',
    render: (v) => (
      <Tag color={v === 1 ? 'cyan' : 'purple'}>Phase {v}</Tag>
    ),
  },
  {
    title: 'Reads',
    dataIndex: 'input_type',
    render: (v) => <Tag>{v}</Tag>,
  },
  {
    title: 'Writes',
    dataIndex: 'output_type',
    render: (v) => <Tag>{v}</Tag>,
  },
  {
    title: 'Requires EN',
    dataIndex: 'requires_en',
    render: (v) => <Badge status={v ? 'warning' : 'default'} text={v ? 'Yes' : 'No'} />,
  },
  {
    title: 'Description',
    dataIndex: 'node_id',
    render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{NODE_DESCRIPTIONS[v]}</Text>,
  },
]

export function FlowCataloguePage() {
  const { data, isLoading, error } = useFlows()

  if (error) return <Alert type="error" message={error.message} />

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={24}>
      <Title level={4} style={{ margin: 0 }}>Flow Catalogue</Title>

      <Row gutter={24}>
        <Col xs={24} xl={14}>
          <Card title={`Processing Nodes (${data?.count ?? '…'})`} size="small">
            {isLoading ? (
              <Skeleton active />
            ) : (
              <Table
                dataSource={data?.nodes}
                columns={COLUMNS}
                rowKey="node_id"
                size="small"
                pagination={false}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card title="Full Topology (all paths)" size="small">
            <DagGraph
              plan={FULL_PLAN}
              currentStep={null}
              stepResults={{}}
              height={380}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              Shows maximum path: YouTube → Download → STT → all Phase 2 branches in parallel.
              Text input skips the ingest chain.
            </Text>
          </Card>
        </Col>
      </Row>

      <Card title="Valid Output Types" size="small">
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : (
          <Space wrap size={16}>
            {(data?.valid_outputs ?? []).map((o) => (
              <div key={o} style={{ background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 8, padding: '8px 16px', minWidth: 180 }}>
                <Tag style={{ marginBottom: 4 }}>{o}</Tag>
                <div>
                  <Text strong style={{ fontSize: 13 }}>{OUTPUT_LABELS[o as OutputType]}</Text>
                </div>
                <Text type="secondary" style={{ fontSize: 12 }}>{OUTPUT_DESCRIPTIONS[o as OutputType]}</Text>
              </div>
            ))}
          </Space>
        )}
      </Card>
    </Space>
  )
}
