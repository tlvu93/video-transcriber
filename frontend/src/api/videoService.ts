import axios, { type AxiosProgressEvent } from "axios";
import type {
  JobAttempt,
  PaginatedResponse,
  SearchResult,
  SummarizationJob,
  Summary,
  Transcript,
  TranscriptComment,
  TranscriptRevision,
  TranslationGlossaryTerm,
  TranscriptionJob,
  TranscriptSegmentsUpdatePayload,
  TranslatedTranscript,
  TranslationJob,
  UnifiedJob,
  Video,
  VideoListPage,
} from "../types/domain";

const apiClient = axios.create({
  baseURL: "/api",
});

interface YoutubeDownloadRequest {
  url: string;
}

interface CreateTranscriptionJobPayload {
  video_id: string;
}

interface CreateSummarizationJobPayload {
  content_profile?: "generic" | "interview" | "lecture" | "meeting" | "podcast";
  transcript_id: string;
}

interface UpdateVideoPayload {
  status?: string;
  video_metadata?: Record<string, unknown>;
}

interface CreateTranslationJobPayload {
  glossary_terms?: TranslationGlossaryTerm[];
  source_language?: string;
  style_guide?: string;
  target_language: string;
  transcript_id: string;
}

interface CreateTranslationJobOptions {
  glossaryTerms?: TranslationGlossaryTerm[];
  sourceLanguage?: string | null;
  styleGuide?: string | null;
}

interface PaginationParams {
  limit?: number;
  offset?: number;
}

interface VideoListParams extends PaginationParams {
  dateWindowDays?: number;
  query?: string;
  sort?: "name" | "newest" | "oldest";
  statusGroup?: "all" | "failed" | "processing" | "ready";
}

interface TranscriptExportParams {
  format: "ass" | "json" | "review_package" | "srt" | "txt" | "vtt";
  includeSpeakers?: boolean;
  includeTimestamps?: boolean;
}

interface TranscriptCommentCreatePayload {
  author_name?: string;
  body: string;
  segment_id?: number;
  timestamp_seconds?: number;
}

interface SearchTranscriptParams extends PaginationParams {
  languageCode?: string;
  query: string;
  reviewStatus?: "approved" | "draft" | "in_review" | "needs_changes";
  speaker?: string;
  videoId?: string;
  videoTitle?: string;
}

function buildPaginationSearch(params?: PaginationParams): URLSearchParams {
  const search = new URLSearchParams();

  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit));
  }

  if (params?.offset !== undefined) {
    search.set("offset", String(params.offset));
  }

  return search;
}

function appendPaginationSearch(path: string, params?: PaginationParams): string {
  const search = buildPaginationSearch(params);
  const queryString = search.toString();
  return queryString ? `${path}?${queryString}` : path;
}

function resolveDownloadFilename(
  contentDispositionHeader: string | undefined,
  fallbackFilename: string
): string {
  if (!contentDispositionHeader) {
    return fallbackFilename;
  }

  const utf8FilenameMatch = contentDispositionHeader.match(
    /filename\*=UTF-8''([^;]+)/
  );
  if (utf8FilenameMatch?.[1]) {
    return decodeURIComponent(utf8FilenameMatch[1]);
  }

  const filenameMatch = contentDispositionHeader.match(/filename="?([^"]+)"?/);
  return filenameMatch?.[1] ?? fallbackFilename;
}

async function triggerBrowserDownload(
  path: string,
  search: URLSearchParams,
  fallbackFilename: string
): Promise<void> {
  const response = await apiClient.get<Blob>(path, {
    params: Object.fromEntries(search.entries()),
    responseType: "blob",
  });

  if (typeof document === "undefined") {
    return;
  }

  const downloadUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = resolveDownloadFilename(
    response.headers["content-disposition"],
    fallbackFilename
  );
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 0);
}

export async function fetchVideoListPage(
  params: VideoListParams = {}
): Promise<VideoListPage> {
  const search = buildPaginationSearch(params);

  if (params.statusGroup) {
    search.set("status_group", params.statusGroup);
  }

  if (params.dateWindowDays !== undefined) {
    search.set("date_window_days", String(params.dateWindowDays));
  }

  if (params.sort) {
    search.set("sort", params.sort);
  }

  if (params.query?.trim()) {
    search.set("q", params.query.trim());
  }

  const queryString = search.toString();
  const response = await apiClient.get<VideoListPage>(
    queryString ? `/videos/?${queryString}` : "/videos/"
  );
  return response.data;
}

export async function fetchVideos(
  params: PaginationParams = { limit: 100, offset: 0 }
): Promise<Video[]> {
  const response = await apiClient.get<VideoListPage>(
    appendPaginationSearch("/videos/", params)
  );
  return response.data.items;
}

export async function downloadYoutubeVideo(url: string): Promise<Video> {
  const response = await apiClient.post<
    Video,
    { data: Video },
    YoutubeDownloadRequest
  >("/videos/youtube", { url });
  return response.data;
}

export async function uploadVideo(
  file: File,
  onUploadProgress?: (progressEvent: AxiosProgressEvent) => void
): Promise<Video> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<Video>("/videos/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress,
  });

  return response.data;
}

export async function fetchVideoById(videoId: string): Promise<Video> {
  const response = await apiClient.get<Video>(`/videos/${videoId}`);
  return response.data;
}

export async function updateVideo(
  videoId: string,
  payload: UpdateVideoPayload
): Promise<Video> {
  const response = await apiClient.patch<Video>(`/videos/${videoId}`, payload);
  return response.data;
}

export async function createTranscriptionJob(
  videoId: string
): Promise<TranscriptionJob> {
  const response = await apiClient.post<
    TranscriptionJob,
    { data: TranscriptionJob },
    CreateTranscriptionJobPayload
  >("/transcription-jobs/", { video_id: videoId });

  return response.data;
}

export async function fetchTranscriptsByVideoId(
  videoId: string
): Promise<Transcript[]> {
  const search = buildPaginationSearch({ limit: 100, offset: 0 });
  search.set("video_id", videoId);
  const response = await apiClient.get<PaginatedResponse<Transcript>>(
    `/transcripts/?${search.toString()}`
  );
  return response.data.items;
}

export async function downloadTranscript(
  transcriptId: string
): Promise<Transcript> {
  const response = await apiClient.get<Transcript>(
    `/transcripts/${transcriptId}`
  );
  return response.data;
}

export async function fetchSummariesByTranscriptId(
  transcriptId: string
): Promise<Summary[]> {
  const search = buildPaginationSearch({ limit: 100, offset: 0 });
  search.set("transcript_id", transcriptId);
  const response = await apiClient.get<PaginatedResponse<Summary>>(
    `/summaries/?${search.toString()}`
  );
  return response.data.items;
}

export async function fetchTranscriptionJobs(
  videoId: string
): Promise<TranscriptionJob[]> {
  const search = buildPaginationSearch({ limit: 100, offset: 0 });
  search.set("video_id", videoId);
  const response = await apiClient.get<PaginatedResponse<TranscriptionJob>>(
    `/transcription-jobs?${search.toString()}`
  );
  return response.data.items;
}

export async function retryTranscriptionJob(
  jobId: string
): Promise<TranscriptionJob> {
  const response = await apiClient.post<TranscriptionJob>(
    `/transcription-jobs/${jobId}/retry`
  );
  return response.data;
}

export async function fetchSummarizationJobs(
  transcriptId: string
): Promise<SummarizationJob[]> {
  const search = buildPaginationSearch({ limit: 100, offset: 0 });
  search.set("transcript_id", transcriptId);
  const response = await apiClient.get<PaginatedResponse<SummarizationJob>>(
    `/summarization-jobs?${search.toString()}`
  );
  return response.data.items;
}

export async function createSummarizationJob(
  transcriptId: string,
  options?: {
    contentProfile?: "generic" | "interview" | "lecture" | "meeting" | "podcast";
  }
): Promise<SummarizationJob> {
  const response = await apiClient.post<
    SummarizationJob,
    { data: SummarizationJob },
    CreateSummarizationJobPayload
  >("/summarization-jobs/", {
    transcript_id: transcriptId,
    content_profile: options?.contentProfile,
  });
  return response.data;
}

export function fetchTranslatedTranscripts(
  transcriptId: string
): Promise<TranslatedTranscript[]>;
export function fetchTranslatedTranscripts(
  transcriptId: string,
  language: string | null | undefined
): Promise<TranslatedTranscript | null>;
export async function fetchTranslatedTranscripts(
  transcriptId: string,
  language?: string | null
): Promise<TranslatedTranscript[] | TranslatedTranscript | null> {
  const search = new URLSearchParams({ transcript_id: transcriptId });

  if (language) {
    search.set("language", language);
  }

  search.set("limit", "100");
  search.set("offset", "0");

  const response = await apiClient.get<PaginatedResponse<TranslatedTranscript>>(
    `/translated-transcripts/?${search.toString()}`
  );

  if (language) {
    return response.data.items[0] ?? null;
  }

  return response.data.items;
}

export async function updateTranscriptSegments(
  transcriptId: string,
  payload: TranscriptSegmentsUpdatePayload
): Promise<Transcript> {
  const response = await apiClient.put<Transcript>(
    `/transcripts/${transcriptId}/segments`,
    payload
  );
  return response.data;
}

export async function updateTranscriptSpeakerAliases(
  transcriptId: string,
  speakerAliases: Record<string, string>
): Promise<Transcript> {
  const response = await apiClient.put<Transcript>(
    `/transcripts/${transcriptId}/speaker-aliases`,
    {
      speaker_aliases: speakerAliases,
    }
  );
  return response.data;
}

export async function fetchTranscriptRevisions(
  transcriptId: string
): Promise<TranscriptRevision[]> {
  const response = await apiClient.get<TranscriptRevision[]>(
    `/transcripts/${transcriptId}/revisions`
  );
  return response.data;
}

export async function restoreTranscriptRevision(
  transcriptId: string,
  revisionId: string
): Promise<Transcript> {
  const response = await apiClient.post<Transcript>(
    `/transcripts/${transcriptId}/revisions/${revisionId}/restore`
  );
  return response.data;
}

export async function updateTranscriptReview(
  transcriptId: string,
  payload: {
    review_assignee?: string | null;
    review_status: "approved" | "draft" | "in_review" | "needs_changes";
  }
): Promise<Transcript> {
  const response = await apiClient.patch<Transcript>(
    `/transcripts/${transcriptId}/review`,
    payload
  );
  return response.data;
}

export async function fetchTranscriptComments(
  transcriptId: string
): Promise<TranscriptComment[]> {
  const response = await apiClient.get<TranscriptComment[]>(
    `/transcripts/${transcriptId}/comments`
  );
  return response.data;
}

export async function createTranscriptComment(
  transcriptId: string,
  payload: TranscriptCommentCreatePayload
): Promise<TranscriptComment> {
  const response = await apiClient.post<TranscriptComment>(
    `/transcripts/${transcriptId}/comments`,
    payload
  );
  return response.data;
}

export async function deleteTranscriptComment(commentId: string): Promise<void> {
  await apiClient.delete(`/transcript-comments/${commentId}`);
}

export async function downloadTranscriptExport(
  transcriptId: string,
  params: TranscriptExportParams
): Promise<void> {
  const search = new URLSearchParams({ format: params.format });
  search.set(
    "include_timestamps",
    String(params.includeTimestamps ?? true)
  );
  search.set("include_speakers", String(params.includeSpeakers ?? true));
  await triggerBrowserDownload(
    `/transcripts/${transcriptId}/export`,
    search,
    `transcript-${transcriptId}.${params.format === "review_package" ? "zip" : params.format}`
  );
}

export async function downloadTranslatedTranscriptExport(
  translatedTranscriptId: string,
  params: TranscriptExportParams
): Promise<void> {
  const search = new URLSearchParams({ format: params.format });
  search.set(
    "include_timestamps",
    String(params.includeTimestamps ?? true)
  );
  search.set("include_speakers", String(params.includeSpeakers ?? true));
  await triggerBrowserDownload(
    `/translated-transcripts/${translatedTranscriptId}/export`,
    search,
    `translated-transcript-${translatedTranscriptId}.${params.format}`
  );
}

export async function updateTranslatedTranscriptSegments(
  translatedTranscriptId: string,
  payload: TranscriptSegmentsUpdatePayload
): Promise<TranslatedTranscript> {
  const response = await apiClient.put<TranslatedTranscript>(
    `/translated-transcripts/${translatedTranscriptId}/segments`,
    payload
  );
  return response.data;
}

export async function createTranslationJob(
  transcriptId: string,
  targetLanguage: string,
  options: CreateTranslationJobOptions = {}
): Promise<TranslationJob> {
  const payload: CreateTranslationJobPayload = {
    transcript_id: transcriptId,
    target_language: targetLanguage,
  };

  if (options.sourceLanguage) {
    payload.source_language = options.sourceLanguage;
  }

  if (options.styleGuide?.trim()) {
    payload.style_guide = options.styleGuide.trim();
  }

  if (options.glossaryTerms?.length) {
    payload.glossary_terms = options.glossaryTerms;
  }

  const response = await apiClient.post<
    TranslationJob,
    { data: TranslationJob },
    CreateTranslationJobPayload
  >("/translation-jobs/", payload);

  return response.data;
}

export async function fetchTranslationJobs(
  transcriptId: string
): Promise<TranslationJob[]> {
  const search = buildPaginationSearch({ limit: 100, offset: 0 });
  search.set("transcript_id", transcriptId);
  const response = await apiClient.get<PaginatedResponse<TranslationJob>>(
    `/translation-jobs?${search.toString()}`
  );
  return response.data.items;
}

export async function fetchUnifiedJobs(params: {
  jobType?: "summarization" | "transcription" | "translation";
  limit?: number;
  offset?: number;
  status?: string;
  subjectId?: string;
  subjectType?: "transcript" | "video";
} = {}): Promise<PaginatedResponse<UnifiedJob>> {
  const search = buildPaginationSearch({
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
  });

  if (params.jobType) {
    search.set("job_type", params.jobType);
  }
  if (params.status) {
    search.set("status", params.status);
  }
  if (params.subjectType) {
    search.set("subject_type", params.subjectType);
  }
  if (params.subjectId) {
    search.set("subject_id", params.subjectId);
  }

  const response = await apiClient.get<PaginatedResponse<UnifiedJob>>(
    `/jobs?${search.toString()}`
  );
  return response.data;
}

export async function fetchJobAttempts(jobId: string): Promise<JobAttempt[]> {
  const response = await apiClient.get<JobAttempt[]>(`/jobs/${jobId}/attempts`);
  return response.data;
}

export async function cancelUnifiedJob(jobId: string): Promise<UnifiedJob> {
  const response = await apiClient.post<UnifiedJob>(`/jobs/${jobId}/cancel`);
  return response.data;
}

export async function retryUnifiedJob(jobId: string): Promise<UnifiedJob> {
  const response = await apiClient.post<UnifiedJob>(`/jobs/${jobId}/retry`);
  return response.data;
}

export async function searchTranscripts(
  params: SearchTranscriptParams
): Promise<SearchResult[]> {
  const search = buildPaginationSearch({
    limit: params.limit ?? 20,
    offset: params.offset ?? 0,
  });
  search.set("q", params.query);
  if (params.languageCode?.trim()) {
    search.set("language_code", params.languageCode.trim());
  }
  if (params.reviewStatus) {
    search.set("review_status", params.reviewStatus);
  }
  if (params.speaker?.trim()) {
    search.set("speaker", params.speaker.trim());
  }
  if (params.videoId?.trim()) {
    search.set("video_id", params.videoId.trim());
  }
  if (params.videoTitle?.trim()) {
    search.set("video_title", params.videoTitle.trim());
  }
  const response = await apiClient.get<PaginatedResponse<SearchResult>>(
    `/search?${search.toString()}`
  );
  return response.data.items;
}
