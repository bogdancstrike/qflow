import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Input, Form, Button, Alert, Space, Typography, message, Segmented, Divider,
} from 'antd'
import { SendOutlined, FileAddOutlined, YoutubeOutlined, FontSizeOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useDropzone } from 'react-dropzone'
import { tasksApi } from '@/api/tasks'
import type { OutputType } from '@/types'
import { OutputSelector } from './OutputSelector'

const { TextArea } = Input
const { Text, Title } = Typography

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
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <div
        {...getRootProps()}
        style={{
          border: `1px dashed ${isDragActive ? '#1890ff' : '#d9d9d9'}`,
          borderRadius: 4,
          padding: '32px 24px',
          textAlign: 'center',
          background: isDragActive ? '#f0faff' : '#fafafa',
          cursor: 'pointer',
          transition: 'all 0.3s',
        }}
      >
        <input {...getInputProps()} />
        <Space direction="vertical" size={8}>
          <FileAddOutlined style={{ fontSize: 24, color: isDragActive ? '#1890ff' : '#8c8c8c' }} />
          <Text strong style={{ fontSize: 13, display: 'block' }}>
            {isDragActive ? 'Drop file' : 'Click or drag media file to upload'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Exts: {ACCEPTED_EXTS.slice(0, 6).join(', ')} ...
          </Text>
        </Space>
      </div>
      {dropped && (
        <Alert
          type="success"
          message={<Text strong style={{ fontSize: 13 }}>{dropped}</Text>}
          showIcon
          closable
          onClose={() => { setDropped(null); onFile('') }}
        />
      )}
      <Input
        placeholder="Or server path (/tmp/audio.mp3)"
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
      messageApi.success('Pipeline initialized')
      navigate(`/tasks/${task.id}`)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const validate = (): string | null => {
    if (outputs.length === 0) return 'Please select at least one analysis output.'
    if (tab === 'text' && !textInput.trim()) return 'Input text is required.'
    if (tab === 'file' && !filePath.trim()) return 'Source file path is required.'
    if (tab === 'youtube') {
      if (!youtubeUrl.trim()) return 'YouTube URL is required.'
      if (!youtubeUrl.match(/youtube\.com|youtu\.be/)) return 'Must be a valid YouTube/YouTu.be URL.'
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
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        {/* Input Selector Section */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: 12, fontSize: 14 }}>1. SOURCE CONTENT</Text>
          <Segmented
            block
            size="large"
            value={tab}
            onChange={(v) => { setTab(v as typeof tab); setError(null) }}
            options={[
              { label: 'Plain Text', value: 'text', icon: <FontSizeOutlined /> },
              { label: 'Media File', value: 'file', icon: <FileAddOutlined /> },
              { label: 'YouTube URL', value: 'youtube', icon: <YoutubeOutlined /> },
            ]}
          />
          
          <div style={{ marginTop: 20 }}>
            {tab === 'text' && (
              <TextArea
                rows={10}
                placeholder="Enter or paste content for AI analysis..."
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                showCount
                maxLength={50000}
                style={{ borderRadius: 2 }}
              />
            )}
            {tab === 'file' && <FileDropzone onFile={setFilePath} />}
            {tab === 'youtube' && (
              <Input
                size="large"
                placeholder="https://www.youtube.com/watch?v=..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                prefix={<YoutubeOutlined style={{ color: '#ff4d4f' }} />}
                allowClear
                style={{ borderRadius: 2 }}
              />
            )}
          </div>
        </div>

        <Divider style={{ margin: '8px 0' }} />

        {/* Output Selector Section */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: 12, fontSize: 14 }}>2. ANALYSIS CONFIGURATION</Text>
          <div style={{ padding: '4px 0' }}>
            <OutputSelector value={outputs} onChange={setOutputs} />
          </div>
        </div>

        {error && (
          <Alert 
            type="error" 
            message={error} 
            showIcon 
            closable 
            onClose={() => setError(null)} 
          />
        )}

        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          loading={isPending}
          onClick={submit}
          size="large"
          block
          style={{ height: 50, fontSize: 16, fontWeight: 500 }}
        >
          Initialize Analytics Pipeline
        </Button>
      </Space>
    </>
  )
}
