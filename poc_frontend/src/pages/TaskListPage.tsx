import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Dayjs } from 'dayjs'
import {
  Table, Space, Button, Select, Segmented, DatePicker, Tag, Typography,
  Popconfirm, message, Tooltip, Badge, Card, theme,
} from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue, SorterResult } from 'antd/es/table/interface'
import {
  ReloadOutlined, DeleteOutlined, EyeOutlined,
  FileTextOutlined, YoutubeOutlined, FileOutlined,
} from '@ant-design/icons'
import { tasksApi } from '@/api/tasks'
import { TaskStatusBadge } from '@/components/shared/TaskStatusBadge'
import { CopyButton } from '@/components/shared/CopyButton'
import { OUTPUT_LABELS } from '@/lib/constants'
import { formatRelativeTime, formatDuration, inputPreview } from '@/lib/formatters'
import type { Task, TaskStatus, InputType, TaskListResponse, OutputType } from '@/types'

const { Text, Title } = Typography
const { RangePicker } = DatePicker

const INPUT_ICON: Record<string, React.ReactNode> = {
  text: <FileTextOutlined />,
  youtube_url: <YoutubeOutlined style={{ color: '#ff4d4f' }} />,
  audio_path: <FileOutlined />,
}

interface Filters {
  status: TaskStatus | ''
  inputType: InputType | ''
  dateRange: [Dayjs | null, Dayjs | null] | null
  sort: string
  cursor: string | undefined
}

const DEFAULT_FILTERS: Filters = {
  status: '',
  inputType: '',
  dateRange: null,
  sort: 'created_at:desc',
  cursor: undefined,
}

export function TaskListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageApi, ctx] = message.useMessage()
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const { token } = theme.useToken()

  const { data, isLoading, isFetching, refetch } = useQuery<TaskListResponse, Error>({
    queryKey: ['tasks', filters],
    queryFn: () =>
      tasksApi.list({
        ...(filters.status ? { status: filters.status } : {}),
        ...(filters.inputType ? { input_type: filters.inputType } : {}),
        ...(filters.dateRange?.[0] ? { created_after: filters.dateRange[0].toISOString() } : {}),
        ...(filters.dateRange?.[1] ? { created_before: filters.dateRange[1].toISOString() } : {}),
        sort: filters.sort,
        cursor: filters.cursor,
        limit: 50,
      }),
    staleTime: 5000,
  })

  const { mutate: deleteOne } = useMutation({
    mutationFn: tasksApi.delete,
    onSuccess: () => {
      messageApi.success('Task deleted')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const { mutate: bulkDelete, isPending: bulkDeleting } = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(ids.map((id) => tasksApi.delete(id)))
    },
    onSuccess: () => {
      messageApi.success(`${selectedIds.length} tasks deleted`)
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const set = (patch: Partial<Filters>) =>
    setFilters((f) => ({ ...f, ...patch, cursor: undefined }))

  const columns: ColumnsType<Task> = [
    {
      title: 'Task ID',
      dataIndex: 'id',
      width: 120,
      render: (v: string) => (
        <Space size={4}>
          <Text code style={{ fontSize: 11, color: token.colorPrimary }}>{v.slice(0, 8).toUpperCase()}</Text>
          <CopyButton text={v} />
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'input_type',
      width: 110,
      render: (v: string) => (
        <Tag color="blue" variant="filled" icon={INPUT_ICON[v] ?? null} style={{ fontSize: 11, fontWeight: 500 }}>
          {v.replace('_', ' ').toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Input Preview',
      dataIndex: 'input_data',
      ellipsis: true,
      render: (v: Record<string, unknown>) => (
        <Tooltip title={JSON.stringify(v)} placement="topLeft">
          <Text style={{ fontSize: 13, color: token.colorTextSecondary }}>{inputPreview(v)}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Outputs',
      dataIndex: 'outputs',
      width: 200,
      render: (v: OutputType[]) => (
        <Space wrap size={4}>
          {v.map((o) => (
            <Tag key={o} variant="filled" style={{ fontSize: 10, margin: 0 }}>
              {OUTPUT_LABELS[o]}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 130,
      render: (v: TaskStatus) => <TaskStatusBadge status={v} showDot />,
    },
    {
      title: 'Age',
      dataIndex: 'created_at',
      width: 100,
      render: (v: string) => (
        <Text style={{ fontSize: 12, color: token.colorTextDescription }}>{formatRelativeTime(v)}</Text>
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 90,
      render: (_: unknown, record: Task) =>
        record.status === 'COMPLETED' || record.status === 'FAILED'
          ? <Text style={{ fontSize: 12, fontWeight: 500 }}>{formatDuration(record.created_at, record.updated_at)}</Text>
          : <Text type="secondary">—</Text>,
    },
    {
      title: '',
      key: 'actions',
      width: 80,
      fixed: 'right',
      render: (_: unknown, record: Task) => (
        <Space size={4} onClick={(e) => e.stopPropagation()}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined style={{ color: token.colorTextDescription }} />}
            onClick={() => navigate(`/tasks/${record.id}`)}
          />
          <Popconfirm
            title="Delete this task?"
            onConfirm={() => deleteOne(record.id)}
            okText="Delete"
            okType="danger"
            placement="bottomRight"
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const handleTableChange = (
    _: TablePaginationConfig,
    tableFilters: Record<string, FilterValue | null>,
    sorter: SorterResult<Task> | SorterResult<Task>[],
  ) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter
    if (s.order) {
      set({ sort: `${s.field}:${s.order === 'ascend' ? 'asc' : 'desc'}` })
    }
    if (tableFilters.status) {
      set({ status: tableFilters.status[0] as TaskStatus })
    }
    if (tableFilters.input_type) {
      set({ inputType: tableFilters.input_type[0] as InputType })
    }
  }

  return (
    <div style={{ width: '100%' }}>
      {ctx}
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <Title level={3} style={{ margin: 0, letterSpacing: '-0.025em', color: token.colorTextHeading }}>Task History</Title>
            <Text style={{ color: token.colorTextSecondary }}>Manage and monitor all orchestrated AI tasks.</Text>
          </div>
          <Space>
             <Button 
               icon={<ReloadOutlined />} 
               onClick={() => refetch()} 
               loading={isFetching}
             >
              Refresh
            </Button>
          </Space>
        </div>

        {/* Toolbar Card */}
        <Card variant="borderless" styles={{ body: { padding: 16 } }}>
          <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
            <Space wrap size={16}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 12, color: token.colorTextSecondary }}>STATUS</Text>
                <Segmented
                  options={[
                    { label: 'All', value: '' },
                    { label: 'Pending', value: 'PENDING' },
                    { label: 'Running', value: 'RUNNING' },
                    { label: 'Completed', value: 'COMPLETED' },
                    { label: 'Failed', value: 'FAILED' },
                  ]}
                  value={filters.status}
                  onChange={(v) => set({ status: v as TaskStatus | '' })}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 12, color: token.colorTextSecondary }}>TYPE</Text>
                <Select
                  value={filters.inputType}
                  onChange={(v) => set({ inputType: v })}
                  options={[
                    { label: 'All types', value: '' },
                    { label: 'Text', value: 'text' },
                    { label: 'File', value: 'audio_path' },
                    { label: 'YouTube', value: 'youtube_url' },
                  ]}
                  style={{ width: 140 }}
                  placeholder="Input type"
                />
              </div>
              <RangePicker
                showTime
                onChange={(v) =>
                  set({ dateRange: v as [Dayjs | null, Dayjs | null] | null })
                }
                style={{ width: 340 }}
              />
              <Button type="text" onClick={() => setFilters(DEFAULT_FILTERS)} style={{ color: token.colorTextSecondary }}>
                Reset Filters
              </Button>
            </Space>

            <Space>
              {selectedIds.length > 0 && (
                <Popconfirm
                  title={`Delete ${selectedIds.length} tasks?`}
                  onConfirm={() => bulkDelete(selectedIds)}
                  okText="Delete all"
                  okType="danger"
                >
                  <Button danger icon={<DeleteOutlined />} loading={bulkDeleting}>
                    Delete Selected ({selectedIds.length})
                  </Button>
                </Popconfirm>
              )}
            </Space>
          </Space>
        </Card>

        {/* Table Card */}
        <Card variant="borderless" styles={{ body: { padding: 0 } }} style={{ overflow: 'hidden' }}>
          <Table
            dataSource={data?.tasks ?? []}
            columns={columns}
            rowKey="id"
            loading={isLoading || isFetching}
            scroll={{ x: 1100 }}
            pagination={false}
            rowSelection={{
              selectedRowKeys: selectedIds,
              onChange: (keys) => setSelectedIds(keys as string[]),
            }}
            onRow={(record) => ({
              onClick: () => navigate(`/tasks/${record.id}`),
              style: { cursor: 'pointer' },
            })}
            onChange={handleTableChange}
            footer={() =>
              data?.has_more ? (
                <div style={{ padding: '12px 0', textAlign: 'center' }}>
                   <Button
                    loading={isFetching}
                    onClick={() => setFilters((f) => ({ ...f, cursor: data.next_cursor ?? undefined }))}
                  >
                    Load More Tasks
                  </Button>
                </div>
              ) : (
                <div style={{ padding: '16px', textAlign: 'center' }}>
                  <Text style={{ fontSize: 13, color: token.colorTextSecondary }}>
                    Showing {data?.tasks.length ?? 0} tasks. End of history.
                  </Text>
                </div>
              )
            }
          />
        </Card>
      </Space>
    </div>
  )
}
