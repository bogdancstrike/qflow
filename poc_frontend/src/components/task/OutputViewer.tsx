import { Typography, Tag, Progress, Space, Divider, theme } from 'antd'
import type { FinalOutput, NerEntity } from '@/types'
import { NER_BG_COLORS, NER_COLORS, OUTPUT_LABELS } from '@/lib/constants'
import { CopyButton } from '@/components/shared/CopyButton'
import { languageName } from '@/lib/formatters'

const { Text, Paragraph, Title } = Typography

// ── NER ──────────────────────────────────────────────────────────────────────

function NerViewer({ entities, sourceText }: { entities: NerEntity[]; sourceText?: string }) {
  const { token } = theme.useToken()
  if (entities.length === 0) return <Text type="secondary">No entities found</Text>

  // Inline highlight
  const highlighted = sourceText ? renderHighlighted(sourceText, entities, token) : null

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {highlighted && (
        <div style={{ lineHeight: 1.8, fontSize: 14, color: token.colorText }}>{highlighted}</div>
      )}
      <Divider style={{ margin: '8px 0' }} />
      <Space wrap>
        {entities.map((e, i) => (
          <Tag key={i} color={NER_COLORS[e.type]} style={{ background: NER_BG_COLORS[e.type], border: 'none' }}>
            <Text style={{ color: NER_COLORS[e.type], fontSize: 11, fontWeight: 600 }}>{e.type}</Text>
            {' '}
            <Text strong style={{ color: NER_COLORS[e.type] }}>{e.text}</Text>
          </Tag>
        ))}
      </Space>
    </Space>
  )
}

function renderHighlighted(text: string, entities: NerEntity[], token: any) {
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
          borderBottom: `2px solid ${NER_COLORS[e.type]}`,
          color: 'inherit',
          padding: '0 2px',
          fontSize: 14,
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
  const { token } = theme.useToken()
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <blockquote style={{ 
        borderLeft: `4px solid ${token.colorPrimary}`, 
        paddingLeft: 16, 
        margin: 0,
        background: token.colorFillAlter,
        padding: '12px 16px',
        borderRadius: `0 ${token.borderRadius}px ${token.borderRadius}px 0`
      }}>
        <Paragraph style={{ margin: 0, fontSize: 15, color: token.colorText }}>{text}</Paragraph>
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
        <Tag key={t} style={{ fontSize: 13, padding: '4px 12px', borderRadius: 4 }}>{t}</Tag>
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
      <Paragraph style={{ margin: 0, fontSize: 15, lineHeight: 1.6 }}>{text}</Paragraph>
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
  const { token } = theme.useToken()
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
            content = <TranslationViewer text={(value as { text: string }).text} />
            break
          default:
            content = <Paragraph code>{JSON.stringify(value, null, 2)}</Paragraph>
        }

        return (
          <div 
            key={key} 
            style={{ 
              background: token.colorBgContainer, 
              borderRadius: token.borderRadiusLG, 
              padding: 24, 
              border: `1px solid ${token.colorBorderSecondary}`,
              boxShadow: token.boxShadowTertiary
            }}
          >
            <Title level={5} style={{ margin: '0 0 16px', color: token.colorTextHeading, textTransform: 'uppercase', fontSize: 13, letterSpacing: '0.05em' }}>
              {label}
            </Title>
            {content}
          </div>
        )
      })}
    </Space>
  )
}
