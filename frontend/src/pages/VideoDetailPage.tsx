import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  createTranscriptionJob,
  fetchTranscriptsByVideoId,
  fetchVideoById,
  updateVideo,
} from "../api/videoService";
import SummarizationJobStatus from "../components/SummarizationJobStatus";
import TranscriptionJobStatus from "../components/TranscriptionJobStatus";
import TranscriptList from "../components/TranscriptList";
import VideoMetadata from "../components/VideoMetadata";
import VideoPlayer from "../components/VideoPlayer";
import VideoSummary from "../components/VideoSummary";
import { useVideoDetailLiveUpdates } from "../hooks/useLiveUpdates";
import type {
  Transcript,
  TranscriptSegment as TranscriptSegmentType,
  TranslatedTranscript,
} from "../types/domain";
import { normalizeTranscript } from "../utils/transcript";

function findActiveSegment(
  segments: TranscriptSegmentType[] | null | undefined,
  currentTime: number
): TranscriptSegmentType | null {
  if (currentTime < 0) {
    return null;
  }

  for (let index = 0; index < (segments ?? []).length; index += 1) {
    const segment = segments?.[index];
    if (!segment) {
      continue;
    }

    const nextSegment = segments?.[index + 1];
    const nextStart = nextSegment
      ? nextSegment.start_time
      : Number.POSITIVE_INFINITY;

    if (currentTime >= segment.start_time && currentTime < nextStart) {
      return segment;
    }
  }

  return null;
}

export default function VideoDetailPage() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [currentTime, setCurrentTime] = useState(0);
  const [displayedTranscript, setDisplayedTranscript] = useState<
    Transcript | TranslatedTranscript | null
  >(null);
  const [seekTime, setSeekTime] = useState<number | null>(null);

  useEffect(() => {
    const startTime = searchParams.get("t");
    if (!startTime) {
      return;
    }

    const parsed = Number(startTime);
    if (Number.isFinite(parsed) && parsed >= 0) {
      setSeekTime(parsed);
    }
  }, [searchParams]);

  const videoQuery = useQuery({
    queryKey: ["video", id],
    queryFn: () => fetchVideoById(id),
    enabled: Boolean(id),
  });
  const transcriptQuery = useQuery({
    queryKey: ["transcripts", id],
    queryFn: () => fetchTranscriptsByVideoId(id),
    enabled: Boolean(id),
    select: (transcripts) => normalizeTranscript(transcripts[0] ?? null),
  });
  useVideoDetailLiveUpdates(id, transcriptQuery.data?.id ?? null);
  const retryMutation = useMutation({
    mutationFn: async () => {
      await createTranscriptionJob(id);
      await updateVideo(id, { status: "pending" });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["video", id] });
      await queryClient.invalidateQueries({
        queryKey: ["transcriptionJobs", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["transcripts", id] });
    },
  });

  useEffect(() => {
    if (transcriptQuery.data) {
      setDisplayedTranscript(transcriptQuery.data);
    }
  }, [transcriptQuery.data]);

  function handleSegmentClick(time: number): void {
    setSeekTime(time);
  }

  function handleTimeUpdate(time: number): void {
    setCurrentTime(time);
  }

  async function handleTranscriptUpdated(): Promise<void> {
    const transcriptId = transcriptQuery.data?.id;
    await queryClient.invalidateQueries({ queryKey: ["transcripts", id] });
    if (transcriptId) {
      await queryClient.invalidateQueries({
        queryKey: ["summaries", transcriptId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["translations", transcriptId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["translationJobs", transcriptId],
      });
    }
  }

  function refreshTranscriptData(): void {
    handleTranscriptUpdated().catch((error) => {
      console.error("Failed to refresh transcript data:", error);
    });
  }

  function getVideoUrl(): string {
    const video = videoQuery.data;
    if (!video) {
      return "";
    }
    return `/api/videos/${video.id}/download`;
  }

  if (videoQuery.isPending || transcriptQuery.isPending) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-blue-500 border-t-2 border-b-2" />
      </div>
    );
  }

  if (videoQuery.isError || transcriptQuery.isError) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="rounded border-red-500 border-l-4 bg-red-100 p-4 text-red-700">
          <p>Failed to load video data. Please try again later.</p>
        </div>
      </div>
    );
  }

  const video = videoQuery.data ?? null;
  const transcript = transcriptQuery.data ?? null;
  const activeSubtitle = findActiveSegment(
    displayedTranscript?.segments,
    currentTime
  );

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <VideoPlayer
            currentTime={seekTime}
            onTimeUpdate={handleTimeUpdate}
            subtitleText={
              currentTime > 0 ? (activeSubtitle?.text ?? null) : null
            }
            videoUrl={getVideoUrl()}
          />
          <div className="mt-4">
            <VideoMetadata
              onRetryTranscription={() => retryMutation.mutateAsync()}
              video={video}
            />
            <TranscriptionJobStatus
              onJobRetried={refreshTranscriptData}
              videoId={id}
            />
            {transcript && (
              <SummarizationJobStatus transcriptId={transcript.id} />
            )}
            {transcript && <VideoSummary transcriptId={transcript.id} />}
          </div>
        </div>
        <div>
          <TranscriptList
            currentTime={currentTime}
            onDisplayedTranscriptChange={setDisplayedTranscript}
            onSegmentClick={handleSegmentClick}
            onTranscriptUpdated={refreshTranscriptData}
            transcript={transcript}
          />
        </div>
      </div>
    </div>
  );
}
