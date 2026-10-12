export interface Capabilities {
  speech_ready: boolean
  translation_ready: boolean
  text_translation_ready: boolean
  classification_ready: boolean
  legal_data_ready: boolean
  models: {
    asr: string
    translation: string
    classifier: string | null
  }
}

export interface SpeechSegment {
  start: number
  end: number
  text: string
}

export interface SpeechProcessResponse {
  transcript_ta: string
  transcript_raw_ta: string
  translation_en: string | null
  language: string
  language_probability: number
  asr_flags: string[]
  asr_status: 'complete' | 'needs_review' | 'failed'
  asr_retried: boolean
  duration_seconds: number
  segments: SpeechSegment[]
  models: {
    asr: string
    translation: string | null
  }
  timing_ms: {
    transcription: number
    translation: number
    total: number
  }
  translation_status: 'complete' | 'not_needed' | 'model_missing' | 'failed'
  translation_error: string | null
  recording_id: string | null
  recording_sha256: string | null
  recording_url: string | null
}

export interface RecordingSummary {
  id: string
  created_at: string
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string
  status: string
  duration_seconds: number | null
  audio_url: string
  drafts: Array<{ record_id: string; created_at: string }>
}

export interface RecordingDetail extends RecordingSummary {
  transcript_ta: string | null
  transcript_raw_ta: string | null
  language: string | null
  asr_flags: string[]
  asr_status: SpeechProcessResponse['asr_status']
  asr_retried: boolean
  translation_en: string | null
}

export interface TextTranslationResponse {
  translation_en: string | null
  translation_status: SpeechProcessResponse['translation_status']
  translation_error: string | null
  model: string | null
}

export interface SectionSuggestion {
  bns_section: string
  ipc_section: string
  offence: string
  cognizable: 'cognizable' | 'non_cognizable' | 'conditional' | 'unknown'
  map_confidence: string
  notes: string
  statute_text: string | null
  bns_heading: string | null
  bns_text: string | null
  retrieval_rank: number | null
}

export interface LegalDecision {
  errors: string[]
  narrative?: string
  suggested_sections: SectionSuggestion[]
  review_flags: Array<Record<string, unknown>>
  cue_hits: Array<Record<string, unknown>>
  route: 'FIR' | 'CSR' | 'OFFICER_REVIEW'
  rationale: string
  [key: string]: unknown
}

export interface DraftResponse {
  decision: LegalDecision
  record: Record<string, unknown>
  if1_text: string
  if1_markdown: string
  narrative_grounded: boolean
  narrative_en: string | null
  translation: Record<string, unknown>
  asr_flags: string[]
  fill_report: Record<string, unknown>
  elapsed_ms: number
  recording_id: string | null
  disclaimer: string
  [key: string]: unknown
}

export type RecordingStatus = 'idle' | 'recording' | 'paused' | 'processing'
