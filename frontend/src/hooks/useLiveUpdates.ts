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

function buildWebSocketUrl(
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

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const queryString = searchParams.toString();
  const pathname = queryString ? `/api/events/ws?${queryString}` : "/api/events/ws";
  return `${protocol}//${window.location.host}${pathname}`;
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

function subscribeToLiveUpdates(
  onEvent: (event: LiveUpdateEvent) => void,
  videoId?: string | null,
  transcriptId?: string | null
): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  let websocket: WebSocket | null = null;
  let eventSource: EventSource | null = null;
  let closed = false;
  let fallbackInitialized = false;

  const handleEventPayload = (rawEvent: string): void => {
    const event = parseLiveUpdateEvent(rawEvent);
    if (!event || event.type === "live.keepalive") {
      return;
    }

    onEvent(event);
  };

  const openEventSource = (): void => {
    if (closed || fallbackInitialized) {
      return;
    }

    fallbackInitialized = true;
    eventSource = new EventSource(buildStreamUrl(videoId, transcriptId));
    eventSource.onmessage = (message) => {
      handleEventPayload(message.data);
    };
    eventSource.onerror = () => {
      if (eventSource?.readyState === EventSource.CLOSED) {
        eventSource.close();
      }
    };
  };

  try {
    websocket = new WebSocket(buildWebSocketUrl(videoId, transcriptId));
    websocket.onmessage = (message) => {
      if (typeof message.data !== "string") {
        return;
      }

      handleEventPayload(message.data);
    };
    websocket.onerror = () => {
      if (!fallbackInitialized) {
        openEventSource();
      }
    };
    websocket.onclose = () => {
      if (!closed && !fallbackInitialized) {
        openEventSource();
      }
    };
  } catch (_error) {
    openEventSource();
  }

  return () => {
    closed = true;
    websocket?.close();
    eventSource?.close();
  };
}

export function useVideoListLiveUpdates(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    return subscribeToLiveUpdates((event) => {
      if (event.type === "video.created" || event.type === "video.updated") {
        invalidateQuery(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
          ["videos"]
        );
      }
    });
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

    return subscribeToLiveUpdates(
      (event) => {
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
      },
      videoId,
      transcriptId
    );
  }, [queryClient, transcriptId, videoId]);
}

export function useUnifiedJobLiveUpdates(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    return subscribeToLiveUpdates((event) => {
      if (event.type !== "job.status.changed") {
        return;
      }

      invalidateQuery(
        (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ["unifiedJobs"]
      );

      if (event.job_id) {
        invalidateQuery(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
          ["jobAttempts", event.job_id]
        );
      }
    });
  }, [queryClient]);
}
