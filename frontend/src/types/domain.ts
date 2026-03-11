export type JobStatus = "pending" | "processing" | "completed" | "failed";

export type VideoStatus =
  | "pending"
  | "processing"
  | "transcribed"
  | "completed"
  | "error"
  | "failed";

export interface VideoMetadata {
  duration?: number;
  file_hash?: string;
  [key: string]: unknown;
}

export interface Video {
  created_at: string;
  file_hash?: string | null;
  filename: string;
  id: string;
  status: VideoStatus | string;
  video_metadata?: VideoMetadata | null;
}

export interface TranscriptSegment {
  end_time: number;
  id: number;
  speaker?: string | null;
  start_time: number;
  text: string;
}

export interface Transcript {
  content: string;
  created_at: string;
  format: string;
  id: string;
  language_code?: string | null;
  segments?: TranscriptSegment[] | null;
  source_type: string;
  status: string;
  video_id: string;
}

export interface Summary {
  content: string;
  created_at: string;
  id: string;
  status: string;
  transcript_id: string;
}

export interface JobErrorDetails {
  error?: string;
  metrics?: TranslationJobMetrics;
  retry_count?: number;
  traceback?: string;
  [key: string]: unknown;
}

export interface TranslationJobMetrics {
  cache_hit?: boolean;
  cache_key_prefix?: string;
  cache_lookup_seconds?: number;
  cache_write_seconds?: number;
  input_characters?: number;
  job_fetch_seconds?: number;
  language_detection_seconds?: number;
  output_characters?: number;
  persist_seconds?: number;
  segment_count?: number;
  source_language?: string;
  target_language?: string;
  total_processing_seconds?: number;
  transcript_fetch_seconds?: number;
  translation_seconds?: number;
  translation_strategy?: string;
}

export interface BaseJob {
  completed_at?: string | null;
  created_at: string;
  error_details?: JobErrorDetails | null;
  id: string;
  processing_time_seconds?: number | null;
  started_at?: string | null;
  status: JobStatus;
}

export interface TranscriptionJob extends BaseJob {
  video_id: string;
}

export interface SummarizationJob extends BaseJob {
  transcript_id: string;
}

export interface TranslationJob extends BaseJob {
  source_language?: string | null;
  target_language: string;
  transcript_id: string;
}

export interface TranslatedTranscript {
  content: string;
  created_at: string;
  id: string;
  language: string;
  segments?: TranscriptSegment[] | null;
  status: string;
  transcript_id: string;
}

export interface SearchResult {
  end_time: number;
  segment_id: number;
  speaker: string;
  start_time: number;
  text: string;
  transcript_id: string;
  video_id: string;
  video_title: string;
}

export interface TranscriptSegmentsUpdatePayload {
  content?: string;
  segments: TranscriptSegment[];
}

export type LiveUpdateEventType =
  | "job.status.changed"
  | "live.connected"
  | "summary.created"
  | "transcript.updated"
  | "transcription.created"
  | "translated_transcript.updated"
  | "translation.created"
  | "video.created"
  | "video.updated";

export interface LiveUpdateEvent {
  filename?: string;
  job_id?: string;
  job_type?: "summarization" | "transcription" | "translation";
  language?: string;
  status?: JobStatus | string;
  summary_id?: string;
  transcript_id?: string;
  translated_transcript_id?: string;
  type: LiveUpdateEventType;
  video_id?: string;
}
