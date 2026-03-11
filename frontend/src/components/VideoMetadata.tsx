import { useState } from "react";
import type { Video } from "../types/domain";
import { getStatusColor } from "../utils/status";

interface VideoMetadataProps {
  onRetryTranscription?: (() => Promise<unknown>) | null;
  video: Video | null;
}

export default function VideoMetadata({
  video,
  onRetryTranscription,
}: VideoMetadataProps) {
  const [retrying, setRetrying] = useState(false);
  if (!video) {
    return <div>Loading metadata...</div>;
  }

  const formattedDate = video.created_at
    ? new Date(video.created_at).toLocaleString()
    : "Unknown date";

  function formatDuration(seconds?: number): string {
    if (!seconds) {
      return "Unknown";
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${remainingSeconds
        .toString()
        .padStart(2, "0")}`;
    }
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  }

  const duration = video.video_metadata?.duration
    ? formatDuration(video.video_metadata.duration)
    : "Unknown";

  async function handleRetry(): Promise<void> {
    if (!onRetryTranscription || retrying) {
      return;
    }

    try {
      setRetrying(true);
      await onRetryTranscription();
    } catch (error) {
      console.error("Error retrying transcription:", error);
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
      <div className="flex items-start justify-between">
        <h2 className="mb-2 font-bold text-gray-800 text-xl dark:text-white">
          {video.filename}
        </h2>

        {onRetryTranscription && (
          <button
            className="rounded bg-blue-500 px-3 py-1 font-semibold text-sm text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={retrying}
            onClick={handleRetry}
            type="button"
          >
            {retrying ? (
              <>
                <span className="mr-1 inline-block animate-spin">⟳</span>
                Retrying...
              </>
            ) : (
              "Retry Transcription"
            )}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-gray-600 text-sm dark:text-gray-300">
        <div>
          <span className="font-semibold">Upload Date:</span> {formattedDate}
        </div>
        <div>
          <span className="font-semibold">Duration:</span> {duration}
        </div>
        <div>
          <span className="font-semibold">Status:</span>{" "}
          <span className={`font-medium ${getStatusColor(video.status)}`}>
            {video.status}
          </span>
        </div>
        <div>
          <span className="font-semibold">File ID:</span>{" "}
          {video.id.substring(0, 8)}...
        </div>
      </div>
    </div>
  );
}
