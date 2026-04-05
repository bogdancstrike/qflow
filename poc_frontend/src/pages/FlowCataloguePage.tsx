import { Typography, Table, Tag, Space, Badge, Skeleton, Alert, Card, Row, Col, theme } from 'antd'
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
  const { token } = theme.useToken()

  if (error) return <Alert type="error" message={error.message} />

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ margin: 0, letterSpacing: '-0.025em', color: token.colorTextHeading }}>System Architecture</Title>
        <Text style={{ color: token.colorTextSecondary }}>Explore the node catalogue and processing topology of the QFlow orchestrator.</Text>
      </div>

      <Row gutter={[20, 20]}>
        <Col span={24}>
          <Card 
            title={<Text strong style={{ fontSize: 14 }}>Processing Node Registry</Text>} 
            variant="borderless"
            styles={{ body: { padding: 0 } }}
          >
            {isLoading ? (
              <div style={{ padding: 24 }}><Skeleton active /></div>
            ) : (
              <Table
                dataSource={data?.nodes}
                columns={COLUMNS}
                rowKey="node_id"
                pagination={false}
              />
            )}
          </Card>
        </Col>

        <Col span={24}>
          <Card 
            title={<Text strong style={{ fontSize: 14 }}>Execution Blueprint (DAG)</Text>} 
            variant="borderless"
          >
            <div style={{ background: token.colorFillAlter, borderRadius: 4, border: `1px solid ${token.colorBorderSecondary}`, padding: 16 }}>
               <DagGraph
                plan={FULL_PLAN}
                currentStep={null}
                stepResults={{}}
                height={300}
              />
            </div>
            <div style={{ marginTop: 12 }}>
              <Text style={{ fontSize: 12, color: token.colorTextSecondary }}>
                <Text strong style={{ color: token.colorTextSecondary }}>Topology overview:</Text> Full processing graph showing YouTube download, STT, and parallel analysis branches.
              </Text>
            </div>
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 8 }}>
        <Title level={4} style={{ marginBottom: 16, letterSpacing: '-0.025em', color: token.colorTextHeading }}>Analytics Definitions</Title>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <Row gutter={[16, 16]}>
            {(data?.valid_outputs ?? []).map((o) => (
              <Col key={o} xs={24} sm={12} lg={8} xl={6}>
                <Card 
                  variant="borderless"
                  styles={{ body: { padding: 16 } }}
                  style={{ height: '100%' }}
                >
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Tag color="blue" variant="filled" style={{ fontSize: 10, fontWeight: 700, margin: 0 }}>{o.toUpperCase()}</Tag>
                      <Badge status="processing" color={token.colorPrimary} />
                    </div>
                    <div>
                      <Title level={5} style={{ margin: '0 0 4px', fontSize: 15, color: token.colorTextHeading }}>{OUTPUT_LABELS[o as OutputType]}</Title>
                      <Text style={{ fontSize: 13, lineHeight: 1.5, display: 'block', color: token.colorTextSecondary }}>
                        {OUTPUT_DESCRIPTIONS[o as OutputType]}
                      </Text>
                    </div>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>
    </Space>
  )
}
