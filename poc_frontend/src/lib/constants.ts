import type { OutputType } from '@/types'

export const OUTPUT_LABELS: Record<OutputType, string> = {
  ner_result: 'Named Entities',
  sentiment_result: 'Sentiment',
  summary: 'Summary',
  iptc_tags: 'IPTC Tags',
  keywords: 'Keywords',
  lang_meta: 'Language',
  text_en: 'English Translation',
}

export const OUTPUT_DESCRIPTIONS: Record<OutputType, string> = {
  ner_result: 'People, locations, and organizations extracted from the text',
  sentiment_result: 'Positive / neutral / negative classification with confidence score',
  summary: 'Condensed summary of the full text',
  iptc_tags: 'IPTC taxonomy topic tags',
  keywords: 'Key terms and phrases extracted from the content',
  lang_meta: 'Detected language of the source text',
  text_en: 'Full English translation of the source text',
}

export const ALL_OUTPUTS: OutputType[] = [
  'ner_result',
  'sentiment_result',
  'summary',
  'iptc_tags',
  'keywords',
  'lang_meta',
  'text_en',
]

export const NODE_LABELS: Record<string, string> = {
  ytdlp_download: 'Download',
  stt: 'Transcribe',
  lang_detect: 'Detect Language',
  translate: 'Translate',
  ner: 'Named Entities',
  sentiment: 'Sentiment',
  summarize: 'Summarize',
  iptc: 'IPTC Classify',
  keyword_extract: 'Keywords',
}

export const NODE_DESCRIPTIONS: Record<string, string> = {
  ytdlp_download: 'Downloads audio from YouTube URL via yt-dlp',
  stt: 'Speech-to-text transcription',
  lang_detect: 'Detects source language',
  translate: 'Translates text to English',
  ner: 'Named entity recognition (requires English)',
  sentiment: 'Sentiment classification (requires English)',
  summarize: 'Text summarization',
  iptc: 'IPTC taxonomy classification',
  keyword_extract: 'Keyword extraction',
}

export const STATUS_COLORS: Record<string, string> = {
  PENDING: 'gold',
  RUNNING: 'blue',
  COMPLETED: 'green',
  FAILED: 'red',
}

export const NER_COLORS: Record<string, string> = {
  PERSON: '#1677ff',
  LOCATION: '#52c41a',
  ORGANIZATION: '#fa8c16',
  MISC: '#722ed1',
}

export const NER_BG_COLORS: Record<string, string> = {
  PERSON: '#e6f4ff',
  LOCATION: '#f6ffed',
  ORGANIZATION: '#fff7e6',
  MISC: '#f9f0ff',
}

export const POLL_INTERVAL_MS = 2000
export const HEALTH_POLL_INTERVAL_MS = 10000
