export type JobStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "cancel_requested"
  | "cancelled";

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
  storage_path?: string | null;
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
  review_assignee?: string | null;
  review_status: "approved" | "draft" | "in_review" | "needs_changes" | string;
  segments?: TranscriptSegment[] | null;
  speaker_aliases?: Record<string, string> | null;
  source_type: string;
  status: string;
  video_id: string;
}

export interface TranscriptRevision {
  content: string;
  created_at: string;
  id: string;
  reason: string;
  revision_number: number;
  segments?: TranscriptSegment[] | null;
  speaker_aliases?: Record<string, string> | null;
  transcript_id: string;
}

export interface TranscriptComment {
  author_name?: string | null;
  body: string;
  created_at: string;
  id: string;
  segment_id?: number | null;
  timestamp_seconds?: number | null;
  transcript_id: string;
}

export interface Summary {
  content: string;
  content_profile: string;
  created_at: string;
  id: string;
  summary_metadata: SummaryMetadata;
  status: string;
  transcript_id: string;
  variants: Record<string, string>;
}

export interface SummaryChapter {
  end_time?: number | null;
  start_time?: number | null;
  summary: string;
  title: string;
}

export interface SummaryHighlight {
  detail: string;
  timestamp_seconds?: number | null;
  title: string;
}

export interface SummaryActionItem {
  due_hint?: string | null;
  owner?: string | null;
  task: string;
}

export interface SummaryEntity {
  description?: string | null;
  entity_type: string;
  name: string;
}

export interface SummaryMetadata {
  action_items?: SummaryActionItem[];
  chapters?: SummaryChapter[];
  content_profile?: string;
  entities?: SummaryEntity[];
  headline?: string;
  highlights?: SummaryHighlight[];
  key_points?: string[];
  keywords?: string[];
  open_questions?: string[];
  overview?: string;
  risks?: string[];
}

export interface TranslationGlossaryTerm {
  notes?: string | null;
  source_term: string;
  target_term: string;
}

export interface TranslationQaMetrics {
  high_cps_warnings?: number;
  long_line_warnings?: number;
  max_chars_per_line?: number;
  max_chars_per_second?: number;
  missing_speaker_warnings?: number;
  overlap_warnings?: number;
  segment_count?: number;
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
  qa_metrics?: TranslationQaMetrics;
  segment_count?: number;
  source_language?: string;
  style_guide_used?: boolean;
  target_language?: string;
  total_processing_seconds?: number;
  transcript_fetch_seconds?: number;
  glossary_term_count?: number;
  translation_seconds?: number;
  translation_strategy?: string;
}

export interface BaseJob {
  completed_at?: string | null;
  created_at: string;
  error_details?: JobErrorDetails | null;
  id: string;
  lease_expires_at?: string | null;
  processing_time_seconds?: number | null;
  started_at?: string | null;
  status: JobStatus;
  worker_id?: string | null;
}

export interface TranscriptionJob extends BaseJob {
  video_id: string;
}

export interface SummarizationJob extends BaseJob {
  content_profile?: string | null;
  transcript_id: string;
}

export interface TranslationJob extends BaseJob {
  glossary_terms?: TranslationGlossaryTerm[] | null;
  source_language?: string | null;
  style_guide?: string | null;
  target_language: string;
  transcript_id: string;
}

export interface UnifiedJob {
  attempt_count: number;
  completed_at?: string | null;
  created_at: string;
  error_details?: JobErrorDetails | null;
  id: string;
  job_type: "summarization" | "transcription" | "translation" | string;
  lease_expires_at?: string | null;
  legacy_job_id: string;
  legacy_job_table: string;
  payload?: Record<string, unknown> | null;
  priority: number;
  processing_time_seconds?: number | null;
  progress?: number | null;
  started_at?: string | null;
  status: JobStatus | "expired" | string;
  subject_id: string;
  subject_type: "transcript" | "video" | string;
  worker_id?: string | null;
}

export interface JobAttempt {
  attempt_number: number;
  completed_at?: string | null;
  created_at: string;
  error_details?: JobErrorDetails | null;
  id: string;
  job_id: string;
  processing_time_seconds?: number | null;
  started_at: string;
  status: JobStatus | "expired" | string;
  worker_id?: string | null;
}

export interface TranslatedTranscript {
  content: string;
  created_at: string;
  glossary_terms?: TranslationGlossaryTerm[] | null;
  id: string;
  language: string;
  qa_metrics?: TranslationQaMetrics | null;
  segments?: TranscriptSegment[] | null;
  style_guide?: string | null;
  status: string;
  transcript_id: string;
}

export interface SearchResult {
  end_time: number;
  language_code?: string | null;
  review_status?: string | null;
  segment_id: number;
  speaker: string;
  start_time: number;
  text: string;
  transcript_id: string;
  video_id: string;
  video_title: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  limit: number;
  offset: number;
  total: number;
}

export interface VideoLibraryStats {
  failed_videos: number;
  processing_videos: number;
  ready_videos: number;
  total_videos: number;
}

export interface VideoListPage extends PaginatedResponse<Video> {
  stats: VideoLibraryStats;
}

export interface TranscriptSegmentsUpdatePayload {
  content?: string;
  segments: TranscriptSegment[];
}

export type LiveUpdateEventType =
  | "job.status.changed"
  | "live.connected"
  | "live.keepalive"
  | "summary.created"
  | "transcript.updated"
  | "transcription.created"
  | "translated_transcript.updated"
  | "translation.created"
  | "video.created"
  | "video.updated";

export interface LiveUpdateEvent {
  attempt_count?: number;
  filename?: string;
  job_id?: string;
  job_type?: "summarization" | "transcription" | "translation";
  language?: string;
  progress?: number;
  status?: JobStatus | string;
  summary_id?: string;
  transcript_id?: string;
  translated_transcript_id?: string;
  type: LiveUpdateEventType;
  video_id?: string;
}
