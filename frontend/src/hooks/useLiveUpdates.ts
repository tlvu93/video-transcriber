import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { LiveUpdateEvent } from "../types/domain";

function buildStreamUrl(
  videoId?: string | null,
  transcriptId?: string | null
): string {
  const searchParams = new URLSearchParams();

  if (videoId) {
    searchParams.set("video_id", videoId);
  }

  if (transcriptId) {
    searchParams.set("transcript_id", transcriptId);
  }

  const queryString = searchParams.toString();
  return queryString
    ? `/api/events/stream?${queryString}`
    : "/api/events/stream";
}

function parseLiveUpdateEvent(rawEvent: string): LiveUpdateEvent | null {
  try {
    return JSON.parse(rawEvent) as LiveUpdateEvent;
  } catch (error) {
    console.error("Failed to parse live update event:", error);
    return null;
  }
}

function invalidateQuery(
  invalidate: (queryKey: readonly unknown[]) => Promise<void>,
  queryKey: readonly unknown[]
): void {
  invalidate(queryKey).catch((error) => {
    console.error("Failed to invalidate query after live update:", error);
  });
}

export function useVideoListLiveUpdates(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const eventSource = new EventSource(buildStreamUrl());
    eventSource.onmessage = (message) => {
      const event = parseLiveUpdateEvent(message.data);
      if (!event) {
        return;
      }

      if (event.type === "video.created" || event.type === "video.updated") {
        invalidateQuery(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
          ["videos"]
        );
      }
    };
    eventSource.onerror = () => {
      if (eventSource.readyState === EventSource.CLOSED) {
        eventSource.close();
      }
    };

    return () => {
      eventSource.close();
    };
  }, [queryClient]);
}

export function useVideoDetailLiveUpdates(
  videoId: string,
  transcriptId?: string | null
): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!videoId) {
      return undefined;
    }

    const eventSource = new EventSource(buildStreamUrl(videoId, transcriptId));
    eventSource.onmessage = (message) => {
      const event = parseLiveUpdateEvent(message.data);
      if (!event) {
        return;
      }

      const invalidate = (queryKey: readonly unknown[]) =>
        invalidateQuery(
          (currentQueryKey) =>
            queryClient.invalidateQueries({ queryKey: currentQueryKey }),
          queryKey
        );

      switch (event.type) {
        case "video.created":
        case "video.updated":
          invalidate(["video", videoId]);
          invalidate(["videos"]);
          break;
        case "transcription.created":
          invalidate(["transcripts", videoId]);
          invalidate(["video", videoId]);
          invalidate(["videos"]);
          break;
        case "summary.created":
          if (event.transcript_id) {
            invalidate(["summaries", event.transcript_id]);
            invalidate(["summarizationJobs", event.transcript_id]);
          }
          break;
        case "translation.created":
          if (event.transcript_id) {
            invalidate(["translations", event.transcript_id]);
            invalidate(["translationJobs", event.transcript_id]);
          }
          break;
        case "transcript.updated":
          invalidate(["transcripts", videoId]);
          break;
        case "translated_transcript.updated":
          if (event.transcript_id) {
            invalidate(["translations", event.transcript_id]);
          }
          break;
        case "job.status.changed":
          if (event.job_type === "transcription") {
            invalidate(["transcriptionJobs", videoId]);
            invalidate(["video", videoId]);

            if (event.status === "completed") {
              invalidate(["transcripts", videoId]);
            }
          }

          if (event.job_type === "summarization" && event.transcript_id) {
            invalidate(["summarizationJobs", event.transcript_id]);

            if (event.status === "completed") {
              invalidate(["summaries", event.transcript_id]);
            }
          }

          if (event.job_type === "translation" && event.transcript_id) {
            invalidate(["translationJobs", event.transcript_id]);

            if (event.status === "completed") {
              invalidate(["translations", event.transcript_id]);
            }
          }
          break;
        default:
          break;
      }
    };
    eventSource.onerror = () => {
      if (eventSource.readyState === EventSource.CLOSED) {
        eventSource.close();
      }
    };

    return () => {
      eventSource.close();
    };
  }, [queryClient, transcriptId, videoId]);
}
