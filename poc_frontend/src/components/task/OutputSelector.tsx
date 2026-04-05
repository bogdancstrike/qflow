import { Space, Button, Typography, Tooltip, Tag } from 'antd'
import type { OutputType } from '@/types'
import { ALL_OUTPUTS, OUTPUT_LABELS, OUTPUT_DESCRIPTIONS } from '@/lib/constants'

const { Text } = Typography
const { CheckableTag } = Tag

interface Props {
  value: OutputType[]
  onChange: (v: OutputType[]) => void
}

export function OutputSelector({ value, onChange }: Props) {
  const allSelected = value.length === ALL_OUTPUTS.length

  const handleChange = (output: OutputType, checked: boolean) => {
    const nextSelectedTags = checked
      ? [...value, output]
      : value.filter((t) => t !== output)
    onChange(nextSelectedTags)
  }

  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Text strong style={{ fontSize: 13, color: '#475569' }}>ANALYTICS ENGINE SELECTION</Text>
        <Button
          size="small"
          type="link"
          onClick={() => onChange(allSelected ? [] : [...ALL_OUTPUTS])}
          style={{ fontSize: 12, fontWeight: 600, padding: 0 }}
        >
          {allSelected ? 'DESELECT ALL' : 'SELECT ALL'}
        </Button>
      </div>
      
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 12px' }}>
        {ALL_OUTPUTS.map((output) => (
          <Tooltip key={output} title={OUTPUT_DESCRIPTIONS[output]} placement="top">
            <CheckableTag
              checked={value.includes(output)}
              onChange={(checked) => handleChange(output, checked)}
              style={{
                padding: '6px 14px',
                fontSize: 13,
                fontWeight: 500,
                borderRadius: 4,
                border: value.includes(output) ? '1px solid #1890ff' : '1px solid #d9d9d9',
                background: value.includes(output) ? '#e6f7ff' : '#fff',
                color: value.includes(output) ? '#1890ff' : '#595959',
                cursor: 'pointer',
                transition: 'all 0.2s',
                margin: 0
              }}
            >
              {OUTPUT_LABELS[output]}
            </CheckableTag>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}
