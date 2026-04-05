import { Typography, Tag, Progress, Space, Alert, Divider } from 'antd'
import type { FinalOutput, NerEntity } from '@/types'
import { NER_BG_COLORS, NER_COLORS, OUTPUT_LABELS } from '@/lib/constants'
import { CopyButton } from '@/components/shared/CopyButton'
import { languageName } from '@/lib/formatters'

const { Text, Paragraph, Title } = Typography

// ── NER ──────────────────────────────────────────────────────────────────────

function NerViewer({ entities, sourceText }: { entities: NerEntity[]; sourceText?: string }) {
  if (entities.length === 0) return <Text type="secondary">No entities found</Text>

  // Inline highlight
  const highlighted = sourceText ? renderHighlighted(sourceText, entities) : null

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {highlighted && (
        <div style={{ lineHeight: 1.8, fontSize: 14 }}>{highlighted}</div>
      )}
      <Divider style={{ margin: '8px 0' }} />
      <Space wrap>
        {entities.map((e, i) => (
          <Tag key={i} color={NER_COLORS[e.type]} style={{ background: NER_BG_COLORS[e.type] }}>
            <Text style={{ color: NER_COLORS[e.type] }}>{e.type}</Text>
            {' '}
            <Text strong>{e.text}</Text>
          </Tag>
        ))}
      </Space>
    </Space>
  )
}

function renderHighlighted(text: string, entities: NerEntity[]) {
  const sorted = [...entities].sort((a, b) => a.start - b.start)
  const parts: React.ReactNode[] = []
  let cursor = 0

  for (const e of sorted) {
    if (e.start > cursor) parts.push(text.slice(cursor, e.start))
    parts.push(
      <mark
        key={e.start}
        style={{
          background: NER_BG_COLORS[e.type],
          border: `1px solid ${NER_COLORS[e.type]}`,
          borderRadius: 3,
          padding: '0 2px',
          fontSize: 13,
        }}
        title={e.type}
      >
        {text.slice(e.start, e.end)}
      </mark>
    )
    cursor = e.end
  }
  if (cursor < text.length) parts.push(text.slice(cursor))
  return parts
}

// ── Sentiment ─────────────────────────────────────────────────────────────────

function SentimentViewer({ sentiment, score }: { sentiment: string; score: number }) {
  const emoji = sentiment === 'positive' ? '😊' : sentiment === 'negative' ? '😞' : '😐'
  const color = sentiment === 'positive' ? 'success' : sentiment === 'negative' ? 'exception' : 'normal'
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <span style={{ fontSize: 32 }}>{emoji}</span>
        <Title level={4} style={{ margin: 0, textTransform: 'capitalize' }}>{sentiment}</Title>
      </Space>
      <Progress
        percent={Math.round(score * 100)}
        status={color}
        format={(p) => `${p}% confidence`}
      />
    </Space>
  )
}

// ── Summary ───────────────────────────────────────────────────────────────────

function SummaryViewer({ text }: { text: string }) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <blockquote style={{ borderLeft: '3px solid #1677ff', paddingLeft: 16, margin: 0 }}>
        <Paragraph style={{ margin: 0, fontSize: 15 }}>{text}</Paragraph>
      </blockquote>
      <CopyButton text={text} />
    </Space>
  )
}

// ── Tags (IPTC / Keywords) ────────────────────────────────────────────────────

function TagViewer({ items }: { items: string[] }) {
  return (
    <Space wrap>
      {items.map((t) => (
        <Tag key={t} style={{ fontSize: 13 }}>{t}</Tag>
      ))}
    </Space>
  )
}

// ── Language ──────────────────────────────────────────────────────────────────

function LangMetaViewer({ language, text }: { language: string; text: string }) {
  return (
    <Space direction="vertical">
      <Space>
        <Tag color="blue" style={{ fontSize: 14 }}>{language.toUpperCase()}</Tag>
        <Text>{languageName(language)}</Text>
      </Space>
      <Text type="secondary" italic>"{text.slice(0, 120)}{text.length > 120 ? '…' : ''}"</Text>
    </Space>
  )
}

// ── Translation ───────────────────────────────────────────────────────────────

function TranslationViewer({ text }: { text: string }) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Paragraph style={{ margin: 0 }}>{text}</Paragraph>
      <CopyButton text={text} />
    </Space>
  )
}

// ── Main OutputViewer ─────────────────────────────────────────────────────────

interface Props {
  finalOutput: FinalOutput
  sourceText?: string
}

export function OutputViewer({ finalOutput, sourceText }: Props) {
  const entries = Object.entries(finalOutput) as [keyof FinalOutput, unknown][]
  if (entries.length === 0) return <Text type="secondary">No outputs available</Text>

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      {entries.map(([key, value]) => {
        const label = OUTPUT_LABELS[key as keyof typeof OUTPUT_LABELS] ?? key

        let content: React.ReactNode = null
        switch (key) {
          case 'ner_result':
            content = <NerViewer entities={(value as { entities: NerEntity[] }).entities} sourceText={sourceText} />
            break
          case 'sentiment_result':
            content = <SentimentViewer {...(value as { sentiment: string; score: number })} />
            break
          case 'summary':
            content = <SummaryViewer text={(value as { summary: string }).summary} />
            break
          case 'iptc_tags':
            content = <TagViewer items={(value as { tags: string[] }).tags} />
            break
          case 'keywords':
            content = <TagViewer items={(value as { keywords: string[] }).keywords} />
            break
          case 'lang_meta':
            content = <LangMetaViewer {...(value as { language: string; text: string })} />
            break
          case 'text_en':
            content = <TranslationViewer text={value as string} />
            break
          default:
            content = <Paragraph code>{JSON.stringify(value, null, 2)}</Paragraph>
        }

        return (
          <div key={key} style={{ background: '#fff', borderRadius: 8, padding: 16, border: '1px solid #f0f0f0' }}>
            <Title level={5} style={{ margin: '0 0 12px' }}>{label}</Title>
            {content}
          </div>
        )
      })}
    </Space>
  )
}
