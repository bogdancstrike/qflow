import { Empty } from 'antd'

interface Props {
  description?: string
  image?: React.ReactNode
}

export function EmptyState({ description = 'No data', image }: Props) {
  return (
    <Empty
      image={image ?? Empty.PRESENTED_IMAGE_SIMPLE}
      description={description}
      style={{ padding: '48px 0' }}
    />
  )
}
