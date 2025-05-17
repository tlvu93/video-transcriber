import { useState } from "react";

const VideoMetadata = ({ video, onRetryTranscription }) => {
  const [retrying, setRetrying] = useState(false);
  if (!video) return <div>Loading metadata...</div>;

  // Format the date
  const formattedDate = video.created_at
    ? new Date(video.created_at).toLocaleString()
    : "Unknown date";

  // Format duration if available in metadata
  const formatDuration = (seconds) => {
    if (!seconds) return "Unknown";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${remainingSeconds
        .toString()
        .padStart(2, "0")}`;
    }
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  // Get duration from metadata if available
  const duration = video.video_metadata?.duration
    ? formatDuration(video.video_metadata.duration)
    : "Unknown";

  // Handle retry button click
  const handleRetry = async () => {
    if (!onRetryTranscription || retrying) return;

    try {
      setRetrying(true);
      await onRetryTranscription();
    } catch (error) {
      console.error("Error retrying transcription:", error);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
      <div className="flex justify-between items-start">
        <h2 className="text-xl font-bold mb-2 text-gray-800 dark:text-white">
          {video.filename}
        </h2>

        {onRetryTranscription && (
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold py-1 px-3 rounded disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {retrying ? (
              <>
                <span className="inline-block animate-spin mr-1">⟳</span>
                Retrying...
              </>
            ) : (
              "Retry Transcription"
            )}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 dark:text-gray-300">
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
};

// Helper function to get color based on status
const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case "completed":
    case "transcribed":
      return "text-green-600 dark:text-green-400";
    case "pending":
    case "processing":
      return "text-yellow-600 dark:text-yellow-400";
    case "error":
    case "failed":
      return "text-red-600 dark:text-red-400";
    default:
      return "text-gray-600 dark:text-gray-400";
  }
};

export default VideoMetadata;
