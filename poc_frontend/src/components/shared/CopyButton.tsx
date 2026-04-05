import { Button, message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'

interface Props {
  text: string
  size?: 'small' | 'middle'
}

export function CopyButton({ text, size = 'small' }: Props) {
  const [api, ctx] = message.useMessage()

  const copy = async () => {
    await navigator.clipboard.writeText(text)
    api.success('Copied!')
  }

  return (
    <>
      {ctx}
      <Button
        type="text"
        size={size}
        icon={<CopyOutlined />}
        onClick={copy}
        style={{ padding: '0 4px' }}
      />
    </>
  )
}
