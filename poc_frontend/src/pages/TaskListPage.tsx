import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Dayjs } from 'dayjs'
import {
  Table, Space, Button, Select, Segmented, DatePicker, Tag, Typography,
  Popconfirm, message, Tooltip, Badge,
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

const { Text } = Typography
const { RangePicker } = DatePicker

const INPUT_ICON: Record<string, React.ReactNode> = {
  text: <FileTextOutlined />,
  youtube_url: <YoutubeOutlined style={{ color: '#ff0000' }} />,
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
      width: 130,
      render: (v: string) => (
        <Space size={2}>
          <Text code style={{ fontSize: 11 }}>{v.slice(0, 8)}</Text>
          <CopyButton text={v} />
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'input_type',
      width: 110,
      filters: [
        { text: 'Text', value: 'text' },
        { text: 'File', value: 'audio_path' },
        { text: 'YouTube', value: 'youtube_url' },
      ],
      render: (v: string) => (
        <Tag icon={INPUT_ICON[v] ?? null}>{v}</Tag>
      ),
    },
    {
      title: 'Input',
      dataIndex: 'input_data',
      ellipsis: true,
      render: (v: Record<string, unknown>) => (
        <Tooltip title={JSON.stringify(v)}>
          <Text type="secondary" style={{ fontSize: 12 }}>{inputPreview(v)}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Outputs',
      dataIndex: 'outputs',
      width: 220,
      render: (v: OutputType[]) => (
        <Space wrap size={2}>
          {v.map((o) => (
            <Tag key={o} style={{ fontSize: 10, margin: 0 }}>{OUTPUT_LABELS[o]}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 120,
      filters: [
        { text: 'Pending', value: 'PENDING' },
        { text: 'Running', value: 'RUNNING' },
        { text: 'Completed', value: 'COMPLETED' },
        { text: 'Failed', value: 'FAILED' },
      ],
      render: (v: TaskStatus) => <TaskStatusBadge status={v} showDot />,
    },
    {
      title: 'Retry',
      dataIndex: 'retry_count',
      width: 64,
      align: 'center',
      render: (v: number) => v > 0 ? <Badge count={v} color="orange" /> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      width: 110,
      sorter: true,
      defaultSortOrder: 'descend',
      render: (v: string) => (
        <Tooltip title={new Date(v).toLocaleString()}>
          <Text style={{ fontSize: 12 }}>{formatRelativeTime(v)}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 90,
      render: (_: unknown, record: Task) =>
        record.status === 'COMPLETED' || record.status === 'FAILED'
          ? <Text style={{ fontSize: 12 }}>{formatDuration(record.created_at, record.updated_at)}</Text>
          : <Text type="secondary">—</Text>,
    },
    {
      title: '',
      key: 'actions',
      width: 80,
      fixed: 'right',
      render: (_: unknown, record: Task) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${record.id}`) }}
          />
          <Popconfirm
            title="Delete this task?"
            onConfirm={(e) => { e?.stopPropagation(); deleteOne(record.id) }}
            okText="Delete"
            okType="danger"
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
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
    <>
      {ctx}
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {/* Toolbar */}
        <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
          <Space wrap>
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
            <RangePicker
              showTime
              onChange={(v) =>
                set({ dateRange: v as [Dayjs | null, Dayjs | null] | null })
              }
              style={{ width: 340 }}
            />
            <Button size="small" onClick={() => setFilters(DEFAULT_FILTERS)}>
              Reset
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
                  Delete {selectedIds.length}
                </Button>
              </Popconfirm>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isFetching}>
              Refresh
            </Button>
          </Space>
        </Space>

        {/* Table */}
        <Table
          dataSource={data?.tasks ?? []}
          columns={columns}
          rowKey="id"
          size="small"
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
              <Button
                block
                size="small"
                loading={isFetching}
                onClick={() => setFilters((f) => ({ ...f, cursor: data.next_cursor ?? undefined }))}
              >
                Load more (has_more = true)
              </Button>
            ) : null
          }
        />

        {/* Row count */}
        <Text type="secondary" style={{ fontSize: 12 }}>
          {data?.tasks.length ?? 0} rows shown
          {data?.has_more ? ' · more available' : ''}
          {selectedIds.length > 0 ? ` · ${selectedIds.length} selected` : ''}
        </Text>
      </Space>
    </>
  )
}
