import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  createTranscriptionJob,
  fetchTranscriptsByVideoId,
  fetchVideoById,
  updateVideo,
} from "../api/videoService";
import ProcessingTimeline from "../components/ProcessingTimeline";
import TranscriptList from "../components/TranscriptList";
import VideoMetadata from "../components/VideoMetadata";
import VideoPlayer from "../components/VideoPlayer";
import VideoSummary from "../components/VideoSummary";
import {
  FeedbackPanel,
  VideoWorkspaceSkeleton,
} from "../components/WorkspaceStates";
import { useVideoDetailLiveUpdates } from "../hooks/useLiveUpdates";
import type {
  Transcript,
  TranscriptSegment as TranscriptSegmentType,
  TranslatedTranscript,
} from "../types/domain";
import { formatRelativeDate } from "../utils/formatters";
import { getVideoStatusMeta } from "../utils/status";
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
    return <VideoWorkspaceSkeleton />;
  }

  if (videoQuery.isError || transcriptQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <FeedbackPanel
          description="The player or transcript data could not be loaded. Please try again."
          eyebrow="Error"
          title="Failed to load this video workspace"
          tone="error"
        />
      </div>
    );
  }

  const video = videoQuery.data ?? null;
  const transcript = transcriptQuery.data ?? null;
  const activeSubtitle = findActiveSegment(
    displayedTranscript?.segments,
    currentTime
  );
  const statusMeta = getVideoStatusMeta(video?.status);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link
            className="inline-flex items-center gap-2 text-muted-foreground text-sm transition hover:text-foreground"
            to="/"
          >
            <svg
              aria-hidden="true"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M10.25 19.25 3.75 12l6.5-7.25M4.5 12h15.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back to library
          </Link>
          <h1 className="mt-4 font-semibold text-3xl text-foreground tracking-tight sm:text-4xl">
            {video?.filename}
          </h1>
          <p className="mt-2 text-muted-foreground">
            Added {formatRelativeDate(video?.created_at)}
          </p>
        </div>

        <span className={`status-chip ${statusMeta.badgeClassName}`}>
          <span className="h-2 w-2 rounded-full bg-current" />
          {statusMeta.label}
        </span>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.9fr)]">
        <div className="min-w-0 space-y-6">
          <VideoPlayer
            currentTime={seekTime}
            onTimeUpdate={handleTimeUpdate}
            subtitleText={
              currentTime > 0 ? (activeSubtitle?.text ?? null) : null
            }
            videoUrl={getVideoUrl()}
          />

          {transcript ? (
            <VideoSummary transcriptId={transcript.id} />
          ) : (
            <section className="panel p-5">
              <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
                Summary
              </p>
              <h2 className="mt-2 font-semibold text-foreground text-xl">
                AI summary
              </h2>
              <p className="mt-3 text-muted-foreground">
                A summary will appear here after the transcript has been
                processed.
              </p>
            </section>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-6 xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)]">
          <VideoMetadata
            onRetryTranscription={() => retryMutation.mutateAsync()}
            transcript={transcript}
            video={video}
          />

          <ProcessingTimeline
            transcriptAvailable={Boolean(transcript)}
            transcriptId={transcript?.id ?? null}
            transcriptSegmentCount={transcript?.segments?.length ?? 0}
            videoId={id}
            videoStatus={video?.status}
          />

          <div className="min-h-[26rem] flex-1 overflow-hidden">
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
    </div>
  );
}
