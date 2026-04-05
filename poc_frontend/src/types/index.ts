export type InputType = 'text' | 'audio_path' | 'youtube_url'
export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type OutputType =
  | 'ner_result'
  | 'sentiment_result'
  | 'summary'
  | 'iptc_tags'
  | 'keywords'
  | 'lang_meta'
  | 'text_en'

export interface NerEntity {
  text: string
  type: 'PERSON' | 'LOCATION' | 'ORGANIZATION' | 'MISC'
  start: number
  end: number
}

export interface FinalOutput {
  ner_result?: { entities: NerEntity[] }
  sentiment_result?: { sentiment: string; score: number }
  summary?: { summary: string }
  iptc_tags?: { tags: string[] }
  keywords?: { keywords: string[] }
  lang_meta?: { language: string; text: string }
  text_en?: string
}

export interface Branch {
  output_type: OutputType
  steps: string[]
}

export interface ExecutionPlan {
  input_type: InputType
  ingest_steps: string[]
  branches: Branch[]
}

export interface Task {
  id: string
  input_type: InputType
  input_data: Record<string, unknown>
  outputs: OutputType[]
  execution_plan: ExecutionPlan
  status: TaskStatus
  current_step: string | null
  step_results: Record<string, unknown>
  workflow_variables: Record<string, unknown>
  final_output: FinalOutput | null
  error: Record<string, unknown> | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface TaskListResponse {
  tasks: Task[]
  next_cursor: string | null
  has_more: boolean
}

export interface TaskStepLog {
  id: string
  task_id: string
  task_ref: string
  task_type: string
  attempt: number
  status: string
  request_payload: unknown
  response_payload: unknown
  branch_taken: string | null
  iteration: number | null
  error_message: string | null
  duration_ms: number | null
  created_at: string
}

export interface LogsResponse {
  logs: TaskStepLog[]
  next_cursor: string | null
  has_more: boolean
}

export interface NodeDef {
  node_id: string
  phase: 1 | 2
  input_type: string
  output_type: string
  requires_en: boolean
}

export interface FlowCatalogue {
  nodes: NodeDef[]
  valid_outputs: OutputType[]
  count: number
}

export interface HealthCheck {
  status: string
  latency_ms: number
}

export interface HealthStatus {
  status: string
  checks: {
    postgres: HealthCheck
    redis: HealthCheck
    kafka: HealthCheck
  }
  dev_mode: boolean
}

export interface CreateTaskPayload {
  input_data: unknown
  outputs: OutputType[]
  input_type?: string
}

export interface ListTasksParams {
  status?: TaskStatus
  input_type?: InputType
  limit?: number
  cursor?: string
  sort?: string
  created_after?: string
  created_before?: string
}
