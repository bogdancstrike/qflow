import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Tabs, Input, Form, Button, Alert, Space, Typography, message,
} from 'antd'
import { SendOutlined, FileAddOutlined, YoutubeOutlined, FontSizeOutlined } from '@ant-design/icons'
import { useDropzone } from 'react-dropzone'
import { tasksApi } from '@/api/tasks'
import type { OutputType } from '@/types'
import { OutputSelector } from './OutputSelector'

const { TextArea } = Input
const { Text } = Typography

const ACCEPTED_EXTS = ['.mp3', '.wav', '.mp4', '.mkv', '.avi', '.webm', '.mov', '.ts', '.flac', '.aac', '.m4a']

function FileDropzone({ onFile }: { onFile: (path: string) => void }) {
  const [dropped, setDropped] = useState<string | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: Object.fromEntries(ACCEPTED_EXTS.map((e) => [`audio/${e.slice(1)}`, [e]])),
    multiple: false,
    onDrop: (files) => {
      if (files[0]) {
        const name = files[0].name
        setDropped(name)
        onFile(name)
      }
    },
  })

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? '#1677ff' : '#d9d9d9'}`,
          borderRadius: 8,
          padding: 32,
          textAlign: 'center',
          background: isDragActive ? '#e6f4ff' : '#fafafa',
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
      >
        <input {...getInputProps()} />
        <Space direction="vertical">
          <FileAddOutlined style={{ fontSize: 32, color: '#8c8c8c' }} />
          <Text type="secondary">
            {isDragActive ? 'Drop the file here' : 'Drag & drop or click to select'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {ACCEPTED_EXTS.join(', ')}
          </Text>
        </Space>
      </div>
      {dropped && (
        <Alert
          type="success"
          message={`Selected: ${dropped}`}
          showIcon
          closable
          onClose={() => { setDropped(null); onFile('') }}
        />
      )}
      <Input
        placeholder="Or type a server file path, e.g. /tmp/audio.mp3"
        onChange={(e) => onFile(e.target.value)}
        allowClear
      />
    </Space>
  )
}

export function TaskForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageApi, ctx] = message.useMessage()

  const [tab, setTab] = useState<'text' | 'file' | 'youtube'>('text')
  const [textInput, setTextInput] = useState('')
  const [filePath, setFilePath] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [outputs, setOutputs] = useState<OutputType[]>(['ner_result', 'summary'])
  const [error, setError] = useState<string | null>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: tasksApi.create,
    onSuccess: (task) => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      messageApi.success('Task created — processing…')
      navigate(`/tasks/${task.id}`)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const validate = (): string | null => {
    if (outputs.length === 0) return 'Select at least one output type'
    if (tab === 'text' && !textInput.trim()) return 'Text cannot be empty'
    if (tab === 'file' && !filePath.trim()) return 'Provide a file path'
    if (tab === 'youtube') {
      if (!youtubeUrl.trim()) return 'YouTube URL cannot be empty'
      if (!youtubeUrl.match(/youtube\.com|youtu\.be/)) return 'Must be a YouTube URL'
    }
    return null
  }

  const submit = () => {
    setError(null)
    const validErr = validate()
    if (validErr) { setError(validErr); return }

    let inputData: unknown
    if (tab === 'text') inputData = { text: textInput }
    else if (tab === 'file') inputData = { file_path: filePath }
    else inputData = { url: youtubeUrl }

    mutate({ input_data: inputData, outputs })
  }

  return (
    <>
      {ctx}
      <Card>
        <Tabs
          activeKey={tab}
          onChange={(k) => { setTab(k as typeof tab); setError(null) }}
          items={[
            {
              key: 'text',
              label: <><FontSizeOutlined /> Text</>,
              children: (
                <Form.Item style={{ marginBottom: 0 }}>
                  <TextArea
                    rows={6}
                    placeholder="Paste text here…"
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    showCount
                    maxLength={50000}
                  />
                </Form.Item>
              ),
            },
            {
              key: 'file',
              label: <><FileAddOutlined /> File Upload</>,
              children: <FileDropzone onFile={setFilePath} />,
            },
            {
              key: 'youtube',
              label: <><YoutubeOutlined /> YouTube URL</>,
              children: (
                <Input
                  placeholder="https://youtube.com/watch?v=… or https://youtu.be/…"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  prefix={<YoutubeOutlined style={{ color: '#ff0000' }} />}
                  allowClear
                />
              ),
            },
          ]}
        />

        <div style={{ marginTop: 16 }}>
          <OutputSelector value={outputs} onChange={setOutputs} />
        </div>

        {error && (
          <Alert type="error" message={error} style={{ marginTop: 12 }} showIcon closable onClose={() => setError(null)} />
        )}

        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={isPending}
          onClick={submit}
          style={{ marginTop: 16 }}
          size="large"
          block
        >
          Submit Task
        </Button>
      </Card>
    </>
  )
}
