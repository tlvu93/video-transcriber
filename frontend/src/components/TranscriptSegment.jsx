const TranscriptSegment = ({ segment, isActive, showTimestamps, onClick }) => {
  // Format time from seconds to [MM:SS] format
  const formatTime = (seconds) => {
    if (seconds === undefined || seconds === null) return "00:00";

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    return `${minutes.toString().padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
  };

  // Ensure segment has all required properties
  const safeSegment = {
    id: segment.id || 0,
    start_time: segment.start_time || 0,
    end_time: segment.end_time || 0,
    text: segment.text || "",
  };

  return (
    <div
      className={`p-2 rounded-md mb-1 cursor-pointer transition-colors ${
        isActive
          ? "bg-blue-100 dark:bg-blue-900 border-l-4 border-blue-500"
          : "hover:bg-gray-100 dark:hover:bg-gray-700"
      }`}
      onClick={() => onClick(safeSegment.start_time)}
    >
      {showTimestamps && (
        <span className="text-xs font-mono text-gray-500 dark:text-gray-400 mr-2">
          [{formatTime(safeSegment.start_time)}]
        </span>
      )}
      <span className="text-gray-800 dark:text-gray-200">
        {safeSegment.text}
      </span>
    </div>
  );
};

export default TranscriptSegment;
