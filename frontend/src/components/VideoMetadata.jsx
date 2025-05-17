const VideoMetadata = ({ video }) => {
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

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
      <h2 className="text-xl font-bold mb-2 text-gray-800 dark:text-white">
        {video.filename}
      </h2>
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
