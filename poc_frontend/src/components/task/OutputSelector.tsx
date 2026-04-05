import { Checkbox, Space, Button, Typography, Tooltip } from 'antd'
import type { OutputType } from '@/types'
import { ALL_OUTPUTS, OUTPUT_LABELS, OUTPUT_DESCRIPTIONS } from '@/lib/constants'

interface Props {
  value: OutputType[]
  onChange: (v: OutputType[]) => void
}

export function OutputSelector({ value, onChange }: Props) {
  const allSelected = value.length === ALL_OUTPUTS.length

  const toggle = (output: OutputType) => {
    if (value.includes(output)) {
      onChange(value.filter((v) => v !== output))
    } else {
      onChange([...value, output])
    }
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <Typography.Text strong>Requested outputs</Typography.Text>
        <Button
          size="small"
          type="link"
          onClick={() => onChange(allSelected ? [] : [...ALL_OUTPUTS])}
        >
          {allSelected ? 'Clear all' : 'Select all'}
        </Button>
      </Space>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {ALL_OUTPUTS.map((output) => (
          <Tooltip key={output} title={OUTPUT_DESCRIPTIONS[output]}>
            <Button
              size="small"
              type={value.includes(output) ? 'primary' : 'default'}
              onClick={() => toggle(output)}
            >
              {OUTPUT_LABELS[output]}
            </Button>
          </Tooltip>
        ))}
      </div>
    </Space>
  )
}
