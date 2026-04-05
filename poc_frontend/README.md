# QFlow Frontend (POC)

React + TypeScript + Vite frontend for the **AI Flow Orchestrator**. Submits tasks, shows live DAG execution, and renders structured AI outputs (NER, sentiment, summary, tags, keywords, translation, language detection).

---

## Stack

| Concern | Library |
|---------|---------|
| Framework | React 19 + TypeScript |
| Build | Vite 8 |
| UI | Ant Design 6 |
| Routing | React Router v7 |
| Data / polling | TanStack Query v5 |
| State | Zustand v5 |
| HTTP | axios |
| DAG graph | ReactFlow 11 + dagre |
| File input | react-dropzone |

---

## Quick Start

```bash
# Prerequisites: backend running at http://localhost:5000
cd poc_frontend
npm install
npm run dev        # http://localhost:3000
```

The Vite dev server proxies `/api/*` to `http://localhost:5000`, so no CORS config is needed.

---

## Pages

| Route | Description |
|-------|-------------|
| `/` | Task submission form (text / file upload / YouTube URL) + live recent-task feed |
| `/tasks` | Full task list with status/type/date filters and cursor pagination |
| `/tasks/:id` | Task detail — live polling, ReactFlow DAG, structured output viewers, step logs |
| `/flows` | Node catalogue table + full-topology static DAG |

---

## Project Structure

```
src/
├── api/              — axios API functions (tasks, flows, health)
├── components/
│   ├── dag/          — DagGraph (ReactFlow + dagre auto-layout)
│   ├── layout/       — AppShell, Sidebar, Topbar (health indicator)
│   ├── logs/         — StepLogTable with expand/collapse payloads
│   ├── shared/       — TaskStatusBadge, CopyButton, EmptyState
│   └── task/         — TaskForm, TaskCard, OutputSelector, OutputViewer
├── hooks/            — useTaskPolling, useFlows
├── lib/              — constants (labels, colors), formatters
├── pages/            — HomePage, TaskListPage, TaskDetailPage, FlowCataloguePage
├── stores/           — healthStore (Zustand, polled every 10s)
└── types/            — shared TypeScript interfaces
```

---

## Key Behaviours

### Task submission
- Three input modes: plain text, file path (drag-and-drop + manual path), YouTube URL
- Output type selector — toggle individual outputs or "Select all"
- On submit: POST `/api/v1/tasks` → redirect to detail page → begin polling

### Task polling
- `useTaskPolling` refetches every 2s while status is `PENDING` or `RUNNING`
- Stops automatically on `COMPLETED` or `FAILED`

### DAG visualization
- ReactFlow graph auto-laid-out via dagre (`LR` direction)
- Node color by execution state: gray (pending), blue-pulse (running), green (completed), red (failed)
- Ingest chain (Phase 1) shown on the left; analysis branches (Phase 2) fan out to the right

### Output viewers
- **NER** — inline entity highlighting by type (PERSON/LOCATION/ORGANIZATION/MISC) with color-coded spans
- **Sentiment** — emoji + label + confidence progress bar
- **Summary** — blockquote + copy button
- **IPTC / Keywords** — pill tag list
- **Language** — code + full name via `Intl.DisplayNames`
- **Translation** — plain text + copy button

### Health indicator
- Topbar badge polls `/api/health` every 10s
- Click to see per-service (PostgreSQL, Redis, Kafka) status and latency

---

## Environment

```bash
# .env.local (optional — default: empty baseURL, relies on Vite proxy)
VITE_API_URL=http://localhost:5000
```

---

## Build

```bash
npm run build      # output: dist/
npm run preview    # serve built output locally
```
