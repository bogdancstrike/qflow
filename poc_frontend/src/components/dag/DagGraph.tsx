import { useMemo, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import dagre from 'dagre'
import 'reactflow/dist/style.css'
import type { ExecutionPlan } from '@/types'
import { NODE_LABELS, NODE_DESCRIPTIONS } from '@/lib/constants'

const NODE_W = 160
const NODE_H = 56

type NodeState = 'pending' | 'running' | 'completed' | 'failed'

const STATE_STYLES: Record<NodeState, React.CSSProperties> = {
  pending: { background: '#fafafa', border: '1px solid #d9d9d9', color: '#8c8c8c' },
  running: { background: '#e6f4ff', border: '2px solid #1677ff', color: '#1677ff', fontWeight: 600 },
  completed: { background: '#f6ffed', border: '1px solid #52c41a', color: '#389e0d' },
  failed: { background: '#fff2f0', border: '1px solid #ff4d4f', color: '#cf1322' },
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
  g.setGraph({ rankdir: 'LR', nodesep: 30, ranksep: 50 })
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
  const { nodes: rawNodes, edges: rawEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []

    const addNode = (id: string, state: NodeState) => {
      nodes.push({
        id,
        type: 'default',
        position: { x: 0, y: 0 },
        data: {
          label: (
            <div style={{ fontSize: 12, lineHeight: 1.4 }}>
              <div style={{ fontWeight: state === 'running' ? 700 : 400 }}>
                {NODE_LABELS[id] ?? id}
              </div>
              <div style={{ fontSize: 10, opacity: 0.7 }}>{id}</div>
            </div>
          ),
        },
        style: { ...STATE_STYLES[state], borderRadius: 8, width: NODE_W, height: NODE_H, display: 'flex', alignItems: 'center', justifyContent: 'center' },
      })
    }

    const addEdge = (source: string, target: string, label?: string) => {
      edges.push({
        id: `${source}->${target}`,
        source,
        target,
        label,
        style: { stroke: '#bfbfbf' },
        animated: currentStep === target,
      })
    }

    // Phase 1 — ingest chain
    let prev: string | null = null
    for (const step of plan.ingest_steps) {
      addNode(step, getNodeState(step, currentStep, stepResults, hasError))
      if (prev) addEdge(prev, step)
      prev = step
    }

    // Phase 2 — branches (de-duplicate nodes that appear in multiple branches)
    const seen = new Set<string>()
    for (const branch of plan.branches) {
      let branchPrev = prev
      for (const step of branch.steps) {
        const nodeId = `${branch.output_type}__${step}`
        // Use bare step id for shared nodes (first occurrence wins positionally but edges are unique)
        const uniqueId = seen.has(step) ? nodeId : step

        if (!seen.has(step)) {
          seen.add(step)
          addNode(step, getNodeState(step, currentStep, stepResults, hasError))
        }

        if (branchPrev) addEdge(branchPrev, uniqueId === nodeId ? step : step, branch.output_type.replace('_result', ''))
        branchPrev = uniqueId === nodeId ? step : step
      }
    }

    return { nodes, edges }
  }, [plan, currentStep, stepResults, hasError])

  const layoutedNodes = useMemo(() => applyDagreLayout(rawNodes, rawEdges), [rawNodes, rawEdges])

  const [nodes] = useNodesState(layoutedNodes)
  const [edges] = useEdgesState(rawEdges)

  return (
    <div style={{ height, background: '#f5f5f5', borderRadius: 8, overflow: 'hidden' }}>
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
        <Background gap={20} color="#e0e0e0" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
