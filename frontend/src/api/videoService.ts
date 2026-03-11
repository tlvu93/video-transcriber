import axios, { type AxiosProgressEvent } from "axios";
import type {
  SearchResult,
  SummarizationJob,
  Summary,
  Transcript,
  TranscriptionJob,
  TranscriptSegmentsUpdatePayload,
  TranslatedTranscript,
  TranslationJob,
  Video,
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
  transcript_id: string;
}

interface UpdateVideoPayload {
  status?: string;
  video_metadata?: Record<string, unknown>;
}

interface CreateTranslationJobPayload {
  source_language?: string;
  target_language: string;
  transcript_id: string;
}

export async function fetchVideos(): Promise<Video[]> {
  const response = await apiClient.get<Video[]>("/videos/");
  return response.data;
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
  const response = await apiClient.get<Transcript[]>(
    `/transcripts/?video_id=${videoId}`
  );
  return response.data;
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
  const response = await apiClient.get<Summary[]>(
    `/summaries/?transcript_id=${transcriptId}`
  );
  return response.data;
}

export async function fetchTranscriptionJobs(
  videoId: string
): Promise<TranscriptionJob[]> {
  const response = await apiClient.get<TranscriptionJob[]>(
    `/transcription-jobs?video_id=${videoId}`
  );
  return response.data;
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
  const response = await apiClient.get<SummarizationJob[]>(
    `/summarization-jobs?transcript_id=${transcriptId}`
  );
  return response.data;
}

export async function createSummarizationJob(
  transcriptId: string
): Promise<SummarizationJob> {
  const response = await apiClient.post<
    SummarizationJob,
    { data: SummarizationJob },
    CreateSummarizationJobPayload
  >("/summarization-jobs/", { transcript_id: transcriptId });
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

  const response = await apiClient.get<TranslatedTranscript[]>(
    `/translated-transcripts/?${search.toString()}`
  );

  if (language) {
    return response.data[0] ?? null;
  }

  return response.data;
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
  sourceLanguage?: string | null
): Promise<TranslationJob> {
  const payload: CreateTranslationJobPayload = {
    transcript_id: transcriptId,
    target_language: targetLanguage,
  };

  if (sourceLanguage) {
    payload.source_language = sourceLanguage;
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
  const response = await apiClient.get<TranslationJob[]>(
    `/translation-jobs?transcript_id=${transcriptId}`
  );
  return response.data;
}

export async function searchTranscripts(
  query: string
): Promise<SearchResult[]> {
  const response = await apiClient.get<SearchResult[]>(
    `/search?q=${encodeURIComponent(query)}`
  );
  return response.data;
}
