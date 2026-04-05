# QFlow Frontend Implementation Plan

## Project Overview

Build a React + TypeScript single-page application for the **AI Flow Orchestrator** — a task pipeline that accepts text, audio/video files, or YouTube URLs, dispatches them through an AI DAG (directed acyclic graph), and returns structured outputs (NER, sentiment, summary, IPTC tags, keywords, translations, language detection).

The frontend is a task management and monitoring UI. Users submit tasks, watch them process in real-time, and inspect structured results.

---

## Tech Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Framework | React 18 + TypeScript | Type safety for structured API responses |
| Build | Vite | Fast HMR, minimal config |
| Routing | React Router v6 | SPA navigation |
| State | Zustand | Lightweight, no boilerplate |
| Data fetching | TanStack Query (React Query) | Polling, cache, loading/error states |
| Styling | Tailwind CSS + shadcn/ui | Utility-first, copy-paste components |
| DAG visualization | ReactFlow | Task execution plan as an interactive graph |
| File upload | react-dropzone | Drag-and-drop file input |
| Notifications | sonner | Toast notifications |
| Icons | lucide-react | Consistent icon set |
| HTTP client | axios | Interceptors, base URL config |
| Linting | ESLint + Prettier | Code consistency |

---

## Backend API Contract

Base URL: `http://localhost:5000`

### Endpoints used

```
POST   /api/v1/tasks                  — create task
GET    /api/v1/tasks                  — list tasks (paginated)
GET    /api/v1/tasks/:id              — get task status + result
DELETE /api/v1/tasks/:id              — cancel/delete task
GET    /api/v1/tasks/:id/logs         — step-level execution logs
GET    /api/v1/flows                  — node catalogue + valid outputs
GET    /api/health                    — system health with dependency latencies
```

### Key types (TypeScript)

```typescript
type InputType = "text" | "audio_path" | "youtube_url";
type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
type OutputType =
  | "ner_result"
  | "sentiment_result"
  | "summary"
  | "iptc_tags"
  | "keywords"
  | "lang_meta"
  | "text_en";

interface Task {
  id: string;
  input_type: InputType;
  input_data: Record<string, unknown>;
  outputs: OutputType[];
  execution_plan: ExecutionPlan;
  status: TaskStatus;
  current_step: string | null;
  step_results: Record<string, unknown>;
  workflow_variables: Record<string, unknown>;
  final_output: FinalOutput | null;
  error: Record<string, unknown> | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

interface ExecutionPlan {
  input_type: InputType;
  ingest_steps: string[];  // e.g. ["ytdlp_download", "stt"]
  branches: Branch[];
}

interface Branch {
  output_type: OutputType;
  steps: string[];  // e.g. ["lang_detect", "translate", "ner"]
}

interface FinalOutput {
  ner_result?: { entities: NerEntity[] };
  sentiment_result?: { sentiment: string; score: number };
  summary?: { summary: string };
  iptc_tags?: { tags: string[] };
  keywords?: { keywords: string[] };
  lang_meta?: { language: string; text: string };
  text_en?: string;
}

interface NerEntity {
  text: string;
  type: "PERSON" | "LOCATION" | "ORGANIZATION" | "MISC";
  start: number;
  end: number;
}

interface TaskStepLog {
  id: string;
  task_id: string;
  task_ref: string;
  task_type: string;
  attempt: number;
  status: string;
  request_payload: unknown;
  response_payload: unknown;
  branch_taken: string | null;
  iteration: number | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
}

interface FlowCatalogue {
  nodes: NodeDef[];
  valid_outputs: OutputType[];
  count: number;
}

interface NodeDef {
  node_id: string;
  phase: 1 | 2;
  input_type: string;
  output_type: string;
  requires_en: boolean;
}

interface HealthStatus {
  status: string;
  checks: {
    postgres: { status: string; latency_ms: number };
    redis: { status: string; latency_ms: number };
    kafka: { status: string; latency_ms: number };
  };
  dev_mode: boolean;
}
```

---

## Application Structure

```
src/
├── api/
│   ├── client.ts          — axios instance with base URL
│   ├── tasks.ts           — task CRUD API functions
│   ├── flows.ts           — flow catalogue API
│   └── health.ts          — health check API
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx   — sidebar + topbar shell
│   │   ├── Sidebar.tsx    — nav links
│   │   └── Topbar.tsx     — title + health indicator
│   ├── task/
│   │   ├── TaskForm.tsx       — input form (text / file / youtube)
│   │   ├── TaskCard.tsx       — compact task row for list view
│   │   ├── TaskDetail.tsx     — full task view (status, outputs, logs)
│   │   ├── TaskStatusBadge.tsx
│   │   ├── OutputViewer.tsx   — renders final_output by type
│   │   ├── NerViewer.tsx      — entity highlighting in text
│   │   ├── SentimentViewer.tsx
│   │   ├── SummaryViewer.tsx
│   │   ├── TagViewer.tsx      — iptc_tags, keywords
│   │   ├── TranslationViewer.tsx
│   │   └── LangMetaViewer.tsx
│   ├── dag/
│   │   ├── DagGraph.tsx       — ReactFlow execution plan visualization
│   │   ├── DagNode.tsx        — custom node component
│   │   └── DagEdge.tsx        — styled edge
│   ├── logs/
│   │   └── StepLogTable.tsx   — paginated step log table
│   └── shared/
│       ├── StatusDot.tsx      — animated dot for PENDING/RUNNING
│       ├── CopyButton.tsx
│       ├── EmptyState.tsx
│       └── ErrorBoundary.tsx
├── pages/
│   ├── HomePage.tsx       — submit form + recent tasks
│   ├── TaskListPage.tsx   — full list with filters
│   ├── TaskDetailPage.tsx — single task view
│   └── FlowCataloguePage.tsx — node catalogue + DAG topology
├── stores/
│   └── healthStore.ts     — global health polling state
├── hooks/
│   ├── useTaskPolling.ts  — polls task until COMPLETED/FAILED
│   ├── useTasks.ts        — list + infinite scroll
│   └── useFlows.ts        — catalogue data
├── lib/
│   ├── formatters.ts      — dates, durations, entity colors
│   └── constants.ts       — output type labels, node descriptions
├── App.tsx
├── main.tsx
└── vite.config.ts
```

---

## Pages

### 1. Home Page (`/`)

**Purpose:** Primary submission form + live feed of recent tasks.

**Layout:** Two-column on desktop. Left: form. Right: live task feed (last 10, auto-refreshing every 3s).

**Form — three input modes (tabs):**

```
[ Text ] [ File Upload ] [ YouTube URL ]
```

- **Text tab**: `<textarea>` for raw text. Character count displayed.
- **File tab**: `react-dropzone` area. Accepts `.mp3 .wav .mp4 .mkv .avi .webm .mov .ts .flac .aac .m4a`. Shows filename + size after drop. On submit, POST to a `/upload` endpoint (or pass local path — see note below).
- **YouTube tab**: Single URL input with validation (must match `youtube.com` or `youtu.be`).

**Output selector (all three tabs share this):**

A grid of toggle-chips, one per valid output type. Labels:

| Output type | Label | Icon |
|-------------|-------|------|
| `ner_result` | Named Entities | tag |
| `sentiment_result` | Sentiment | heart |
| `summary` | Summary | file-text |
| `iptc_tags` | IPTC Tags | layers |
| `keywords` | Keywords | key |
| `lang_meta` | Language | globe |
| `text_en` | English Translation | languages |

At least one output must be selected. "Select All" shortcut.

**Submit flow:**
1. Validate (non-empty input, ≥1 output selected)
2. POST `/api/v1/tasks`
3. Show toast "Task created — processing…"
4. Navigate to `/tasks/:id` for the new task
5. Begin polling

**Live feed (right column):**
- Uses TanStack Query with `refetchInterval: 3000`
- Shows last 10 tasks as `TaskCard` rows
- Each card shows: input type icon, truncated input preview, status badge, elapsed time, output chips
- Clicking a card navigates to `/tasks/:id`

---

### 2. Task List Page (`/tasks`)

**Purpose:** Browse, filter, and manage all tasks.

**Filters (top bar):**
- Status: `All | PENDING | RUNNING | COMPLETED | FAILED` (segmented control)
- Input type: `All | Text | File | YouTube` (dropdown)
- Date range: `created_after` / `created_before` (date pickers)
- Sort: `newest first | oldest first | status`

**Table columns:**
| Column | Content |
|--------|---------|
| ID | First 8 chars, monospace, copy button |
| Input | Icon + truncated preview |
| Outputs | Chip list |
| Status | Colored badge + animated dot for PENDING/RUNNING |
| Created | Relative time (`2 minutes ago`) |
| Duration | `updated_at - created_at` for COMPLETED |
| Actions | View button, Delete button |

**Pagination:** Cursor-based. "Load more" button appends next page (infinite scroll option).

**Bulk delete:** Checkbox column + "Delete selected" button.

---

### 3. Task Detail Page (`/tasks/:id`)

**Purpose:** Full task inspection — status, DAG visualization, outputs, logs.

**Auto-polling:** Uses `useTaskPolling` hook. Polls every 2s while `status` is `PENDING` or `RUNNING`. Stops on `COMPLETED` or `FAILED`.

**Layout:** Three sections stacked vertically.

#### Section A — Task Header
- Task ID (full UUID, copy button)
- Status badge (large)
- Input type + truncated input preview
- Requested outputs (chip list)
- Timestamps: created, updated, duration
- Delete button (with confirmation dialog)

#### Section B — Execution Plan (DAG Visualization)

Uses **ReactFlow** to render the `execution_plan` as a live graph.

**Node rendering:**

Ingest nodes (Phase 1) are rendered left-to-right in a vertical column on the left. Each Phase 2 branch fans out horizontally to the right. The graph auto-layouts using dagre.

Node states:
- Gray: not yet reached
- Blue + pulsing: currently executing (`current_step` matches)
- Green: completed (in `step_results`)
- Red: failed (in `error`)

Node labels use friendly names:

| node_id | Label |
|---------|-------|
| `ytdlp_download` | Download |
| `stt` | Transcribe |
| `lang_detect` | Detect Language |
| `translate` | Translate |
| `ner` | Named Entities |
| `sentiment` | Sentiment |
| `summarize` | Summarize |
| `iptc` | IPTC Classify |
| `keyword_extract` | Keywords |

Hovering a node shows a tooltip with: node ID, input/output types, duration (from step logs if available).

**Graph layout algorithm (dagre):**

```
[start] → [ytdlp_download] → [stt] → [lang_detect] → [translate] → [ner]
                                                    ↘              → [sentiment]
                                                     → [summarize]
                                                     → [iptc]
                                                     → [keyword_extract]
```

Ingest nodes appear before the fan-out. Branches that don't require translation skip the translate node.

#### Section C — Results

Rendered after `status === "COMPLETED"`. One collapsible card per output type in `final_output`.

**NER result (`NerViewer`):**

Renders the original text with entity spans highlighted inline. Color by entity type:

| Type | Color |
|------|-------|
| PERSON | blue |
| LOCATION | green |
| ORGANIZATION | orange |
| MISC | purple |

Below the highlighted text: a table of all entities (text, type, position).

**Sentiment result (`SentimentViewer`):**

Large emoji + label (positive/neutral/negative) + a horizontal confidence bar showing `score`.

**Summary (`SummaryViewer`):**

Blockquote-styled text block. Copy button.

**IPTC tags / Keywords (`TagViewer`):**

Pill badges in a wrapping flex row. Each tag is copyable.

**Language meta (`LangMetaViewer`):**

Language code + full name (use `Intl.DisplayNames`). Shows detected text snippet.

**Translation (`TranslationViewer`):**

Side-by-side: original text on left, English translation on right.

#### Section D — Step Logs

Collapsible section (closed by default). Loads from `GET /api/v1/tasks/:id/logs` on expand.

Table columns: Step | Branch | Attempt | Status | Duration | Timestamp | Error

Paginated with "Load more". Each row expandable to show raw `request_payload` and `response_payload` as JSON.

---

### 4. Flow Catalogue Page (`/flows`)

**Purpose:** Developer reference — shows all nodes, their I/O types, which outputs they produce.

**Left panel:** Node catalogue table

| Node | Phase | Reads | Writes | Requires EN |
|------|-------|-------|--------|-------------|
| ytdlp_download | 1 | youtube_url | audio_path | No |
| stt | 1 | audio_path | text | No |
| ... | ... | ... | ... | ... |

**Right panel:** Interactive full-topology DAG

Shows all 9 nodes connected as a complete static graph (not a specific task's plan). Illustrates the full possible execution space. Nodes colored by phase (Phase 1 = teal, Phase 2 = violet).

**Valid outputs section:** Checklist showing each output type with description and whether it requires English translation.

---

## Polling Strategy

```typescript
// hooks/useTaskPolling.ts
function useTaskPolling(taskId: string) {
  return useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.getTask(taskId),
    refetchInterval: (data) => {
      if (!data) return 2000;
      if (data.status === "COMPLETED" || data.status === "FAILED") return false;
      return 2000;
    },
    staleTime: 0,
  });
}
```

---

## DAG Graph Implementation

```typescript
// components/dag/DagGraph.tsx
// Input: execution_plan + current_step + step_results + error
// Output: ReactFlow graph

function buildNodes(plan: ExecutionPlan, currentStep: string | null, stepResults: Record<string, unknown>) {
  const nodes: Node[] = [];

  // Phase 1 — ingest chain
  plan.ingest_steps.forEach((stepId, i) => {
    nodes.push({
      id: stepId,
      type: "dagNode",
      position: { x: 0, y: i * 100 },
      data: {
        label: NODE_LABELS[stepId],
        state: getNodeState(stepId, currentStep, stepResults),
      },
    });
  });

  // Phase 2 — branches
  plan.branches.forEach((branch, branchIdx) => {
    branch.steps.forEach((stepId, stepIdx) => {
      nodes.push({
        id: `${branch.output_type}__${stepId}`,
        type: "dagNode",
        position: { x: (branchIdx + 1) * 220, y: stepIdx * 100 },
        data: {
          label: NODE_LABELS[stepId],
          state: getNodeState(stepId, currentStep, stepResults),
          outputType: branch.output_type,
        },
      });
    });
  });

  return nodes;
}

type NodeState = "pending" | "running" | "completed" | "failed";

function getNodeState(
  stepId: string,
  currentStep: string | null,
  stepResults: Record<string, unknown>
): NodeState {
  if (stepId in stepResults) return "completed";
  if (stepId === currentStep) return "running";
  return "pending";
}
```

Node visual states (Tailwind classes):
- `pending` → `bg-gray-100 border-gray-300 text-gray-500`
- `running` → `bg-blue-100 border-blue-500 text-blue-700 animate-pulse`
- `completed` → `bg-green-100 border-green-500 text-green-700`
- `failed` → `bg-red-100 border-red-500 text-red-700`

---

## API Client Layer

```typescript
// api/client.ts
import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:5000",
  headers: { "Content-Type": "application/json" },
});

// api/tasks.ts
export const tasksApi = {
  create: (payload: { input_data: unknown; outputs: OutputType[]; input_type?: string }) =>
    apiClient.post<Task>("/api/v1/tasks", payload).then((r) => r.data),

  list: (params: {
    status?: TaskStatus;
    input_type?: InputType;
    limit?: number;
    cursor?: string;
    sort?: string;
    created_after?: string;
    created_before?: string;
  }) => apiClient.get<{ tasks: Task[]; next_cursor: string | null; has_more: boolean }>("/api/v1/tasks", { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Task>(`/api/v1/tasks/${id}`).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/tasks/${id}`).then((r) => r.data),

  getLogs: (id: string, params?: { limit?: number; cursor?: string }) =>
    apiClient.get<{ logs: TaskStepLog[]; next_cursor: string | null; has_more: boolean }>(
      `/api/v1/tasks/${id}/logs`, { params }
    ).then((r) => r.data),
};

export const flowsApi = {
  getCatalogue: () =>
    apiClient.get<FlowCatalogue>("/api/v1/flows").then((r) => r.data),
};

export const healthApi = {
  get: () =>
    apiClient.get<HealthStatus>("/api/health").then((r) => r.data),
};
```

---

## Global Health Indicator

Topbar shows a colored dot polling `/api/health` every 10s:

- Green: all checks OK
- Yellow: any check degraded (latency > 100ms)
- Red: any check down

On hover: popover showing individual service statuses with latencies.

```typescript
// stores/healthStore.ts
const useHealthStore = create<{ health: HealthStatus | null; setHealth: (h: HealthStatus) => void }>(...)

// Topbar.tsx
useQuery({
  queryKey: ["health"],
  queryFn: healthApi.get,
  refetchInterval: 10000,
  onSuccess: useHealthStore.getState().setHealth,
});
```

---

## Environment Config

```
# .env.local
VITE_API_URL=http://localhost:5000
```

---

## Project Scaffolding Commands

```bash
npm create vite@latest qflow-ui -- --template react-ts
cd qflow-ui
npm install \
  @tanstack/react-query \
  react-router-dom \
  zustand \
  axios \
  reactflow \
  react-dropzone \
  sonner \
  lucide-react \
  tailwindcss \
  @tailwindcss/vite \
  clsx \
  tailwind-merge \
  dagre \
  @types/dagre

# shadcn/ui setup
npx shadcn@latest init
npx shadcn@latest add button badge card dialog tabs separator tooltip popover
```

`vite.config.ts` — proxy to backend during dev:

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:5000",
    },
  },
});
```

---

## Implementation Order

### Phase 1 — Core plumbing (Day 1)
1. Vite scaffold + Tailwind + shadcn init
2. `api/client.ts` + all API functions
3. React Router setup with 4 routes
4. `AppShell` with sidebar + topbar
5. `useHealthStore` + topbar health dot

### Phase 2 — Task submission (Day 2)
6. `TaskForm` with text/file/youtube tabs
7. Output type selector chips
8. Submit → POST → toast → redirect
9. `TaskStatusBadge` component

### Phase 3 — Task list (Day 2–3)
10. `TaskListPage` with filter bar
11. `TaskCard` with all columns
12. Cursor pagination / load more
13. Delete with confirmation

### Phase 4 — Task detail + polling (Day 3)
14. `TaskDetailPage` header section
15. `useTaskPolling` hook
16. Results section with all 7 output viewers
17. `StepLogTable` with expand/collapse

### Phase 5 — DAG visualization (Day 4)
18. `DagGraph` with ReactFlow
19. dagre auto-layout
20. `DagNode` with state colors + pulse animation
21. Hover tooltip with node metadata
22. Wire into `TaskDetailPage`

### Phase 6 — Flow catalogue (Day 4)
23. `FlowCataloguePage` with node table
24. Full-topology static DAG

### Phase 7 — Polish (Day 5)
25. Empty states for all list/detail views
26. Error boundaries
27. Mobile responsive layout (sidebar collapses to drawer)
28. Loading skeletons for all data-fetching states
29. Keyboard shortcuts (N = new task, Escape = close dialogs)

---

## Key UX Decisions

**No WebSocket** — polling every 2s is sufficient. Average task takes 1–10s in DEV_MODE; true AI runs take 5–30s. Polling overhead is negligible.

**File upload note** — the backend takes a `file_path` (server-side path). In production, implement a file upload endpoint that receives the binary and returns a server path. In dev, users can type the local path directly.

**NER highlighting** — reconstruct spans from `start`/`end` character offsets in the original text. Overlapping entities are unlikely given the model output but handle gracefully (render as adjacent, non-overlapping).

**Branch isolation in the DAG view** — each Phase 2 branch is a separate column. Nodes with the same `node_id` appearing in multiple branches (e.g. `lang_detect`, `translate`) are de-duplicated visually into a shared fan-out from the last Phase 1 node.

**Cursor pagination** — the backend's `next_cursor` is the ID of the last returned task. Pass it as `cursor` in the next request. Implement as "Load more" button (simpler than true infinite scroll for this use case).
