import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Dayjs } from 'dayjs'
import {
  Table, Space, Button, Select, Segmented, DatePicker, Tag, Typography,
  Popconfirm, message, Tooltip, Badge, Card,
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
      width: 120,
      render: (v: string) => (
        <Space size={4}>
          <Text code style={{ fontSize: 11, color: '#64748b' }}>{v.slice(0, 8).toUpperCase()}</Text>
          <CopyButton text={v} />
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'input_type',
      width: 110,
      render: (v: string) => (
        <Tag color="blue" bordered={false} icon={INPUT_ICON[v] ?? null} style={{ fontSize: 11, fontWeight: 500 }}>
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
          <Text style={{ fontSize: 13, color: '#475569' }}>{inputPreview(v)}</Text>
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
            <Tag key={o} style={{ fontSize: 10, margin: 0, background: '#f1f5f9', border: 'none', color: '#64748b' }}>
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
        <Text style={{ fontSize: 12, color: '#94a3b8' }}>{formatRelativeTime(v)}</Text>
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
            icon={<EyeOutlined style={{ color: '#64748b' }} />}
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

  return (
    <div style={{ width: '100%' }}>
      {ctx}
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <Title level={3} style={{ margin: 0, letterSpacing: '-0.025em' }}>Task History</Title>
            <Text type="secondary">Manage and monitor all orchestrated AI tasks.</Text>
          </div>
          <Space>
             <Button 
               icon={<ReloadOutlined />} 
               onClick={() => refetch()} 
               loading={isFetching}
               style={{ borderRadius: 6 }}
             >
              Refresh
            </Button>
          </Space>
        </div>

        {/* Toolbar Card */}
        <Card bordered={false} bodyStyle={{ padding: 16 }} style={{ boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)' }}>
          <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
            <Space wrap size={16}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 12, color: '#64748b' }}>STATUS</Text>
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
                <Text strong style={{ fontSize: 12, color: '#64748b' }}>TYPE</Text>
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
              <Button type="text" onClick={() => setFilters(DEFAULT_FILTERS)} style={{ color: '#64748b' }}>
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
        <Card bordered={false} bodyStyle={{ padding: 0 }} style={{ boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)', overflow: 'hidden' }}>
          <Table
            dataSource={data?.tasks ?? []}
            columns={columns}
            rowKey="id"
            size="middle"
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
            footer={() =>
              data?.has_more ? (
                <div style={{ padding: '12px 0', textAlign: 'center' }}>
                   <Button
                    loading={isFetching}
                    onClick={() => setFilters((f) => ({ ...f, cursor: data.next_cursor ?? undefined }))}
                    style={{ borderRadius: 6 }}
                  >
                    Load More Tasks
                  </Button>
                </div>
              ) : (
                <div style={{ padding: '16px', textAlign: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
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
