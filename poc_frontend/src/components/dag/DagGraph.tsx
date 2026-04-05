import { useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow'
import dagre from 'dagre'
import { theme } from 'antd'
import 'reactflow/dist/style.css'
import type { ExecutionPlan } from '@/types'
import { NODE_LABELS } from '@/lib/constants'

const NODE_W = 180
const NODE_H = 60

type NodeState = 'pending' | 'running' | 'completed' | 'failed'

const GET_STATE_COLORS = (state: NodeState, token: any) => {
  switch (state) {
    case 'running':
      return { 
        bg: token.colorInfoBg, 
        border: token.colorInfo, 
        text: token.colorInfoText,
        shadow: `0 0 10px ${token.colorInfo}40`
      }
    case 'completed':
      return { 
        bg: token.colorSuccessBg, 
        border: token.colorSuccess, 
        text: token.colorSuccessText,
        shadow: 'none'
      }
    case 'failed':
      return { 
        bg: token.colorErrorBg, 
        border: token.colorError, 
        text: token.colorErrorText,
        shadow: 'none'
      }
    default:
      return { 
        bg: token.colorFillQuaternary, 
        border: token.colorBorder, 
        text: token.colorTextSecondary,
        shadow: 'none'
      }
  }
}

function getNodeState(
  nodeId: string,
  currentStep: string | null,
  stepResults: Record<string, unknown>,
  hasError: boolean,
): NodeState {
  if (hasError && nodeId === currentStep) return 'failed'
  if (nodeId in stepResults) return 'completed'
  if (nodeId === currentStep) return 'running'
  return 'pending'
}

function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 60 })
  g.setDefaultEdgeLabel(() => ({}))

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
  edges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)

  return nodes.map((n) => {
    const { x, y } = g.node(n.id)
    return { ...n, position: { x: x - NODE_W / 2, y: y - NODE_H / 2 } }
  })
}

interface Props {
  plan: ExecutionPlan
  currentStep: string | null
  stepResults: Record<string, unknown>
  hasError?: boolean
  height?: number
}

export function DagGraph({ plan, currentStep, stepResults, hasError = false, height = 320 }: Props) {
  const { token } = theme.useToken()

  const { nodes: rawNodes, edges: rawEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []

    const addNode = (id: string, state: NodeState) => {
      const colors = GET_STATE_COLORS(state, token)
      nodes.push({
        id,
        type: 'default',
        position: { x: 0, y: 0 },
        data: {
          label: (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: colors.text }}>
                {NODE_LABELS[id] ?? id}
              </div>
              <div style={{ fontSize: 10, opacity: 0.6, color: colors.text }}>{id}</div>
            </div>
          ),
        },
        style: { 
          background: colors.bg, 
          border: `1px solid ${colors.border}`, 
          borderRadius: 4, 
          width: NODE_W, 
          height: NODE_H, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          boxShadow: colors.shadow,
          transition: 'all 0.3s'
        },
      })
    }

    const addEdge = (source: string, target: string, label?: string) => {
      edges.push({
        id: `${source}->${target}`,
        source,
        target,
        label,
        type: 'straight', // Straight lines as requested
        labelStyle: { fill: token.colorTextSecondary, fontSize: 10, fontWeight: 500 },
        style: { 
          stroke: currentStep === target ? token.colorInfo : token.colorBorder, 
          strokeWidth: 2 
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: currentStep === target ? token.colorInfo : token.colorBorder,
        },
        animated: currentStep === target,
      })
    }

    // Phase 1
    let prev: string | null = null
    for (const step of plan.ingest_steps) {
      addNode(step, getNodeState(step, currentStep, stepResults, hasError))
      if (prev) addEdge(prev, step)
      prev = step
    }

    // Phase 2
    const seen = new Set<string>()
    for (const branch of plan.branches) {
      let branchPrev = prev
      for (const step of branch.steps) {
        if (!seen.has(step)) {
          seen.add(step)
          addNode(step, getNodeState(step, currentStep, stepResults, hasError))
        }
        if (branchPrev) addEdge(branchPrev, step, branch.output_type.replace('_result', ''))
        branchPrev = step
      }
    }

    return { nodes, edges }
  }, [plan, currentStep, stepResults, hasError, token])

  const layoutedNodes = useMemo(() => applyDagreLayout(rawNodes, rawEdges), [rawNodes, rawEdges])

  const [nodes] = useNodesState(layoutedNodes)
  const [edges] = useEdgesState(rawEdges)

  return (
    <div style={{ 
      height, 
      background: token.colorFillAlter, 
      borderRadius: token.borderRadiusLG, 
      overflow: 'hidden',
      border: `1px solid ${token.colorBorderSecondary}`
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
      >
        <Background gap={20} color={token.colorBorderSecondary} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
