import { useState } from "react";
import TranscriptSegment from "./TranscriptSegment";

const TranscriptList = ({ transcript, currentTime, onSegmentClick }) => {
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  if (!transcript) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
        <p className="text-gray-500 dark:text-gray-400 text-center py-4">
          No transcript available.
        </p>
      </div>
    );
  }

  // Ensure segments array exists
  const segments = transcript.segments || [];

  if (segments.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
            Transcript
          </h3>
        </div>
        <p className="text-gray-500 dark:text-gray-400 text-center py-4">
          {transcript.content ? (
            <span className="text-gray-800 dark:text-gray-200">
              {transcript.content}
            </span>
          ) : (
            "No transcript segments available."
          )}
        </p>
      </div>
    );
  }

  // Filter segments based on search query
  const filteredSegments = searchQuery
    ? segments.filter((segment) =>
        segment.text.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : segments;

  // Find the active segment based on current video time
  const findActiveSegment = () => {
    if (!currentTime) return null;

    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      const nextSegment = segments[i + 1];

      // Ensure we're using the correct field names
      const segmentStart = segment.start_time;
      const nextSegmentStart = nextSegment ? nextSegment.start_time : Infinity;

      if (currentTime >= segmentStart && currentTime < nextSegmentStart) {
        return segment;
      }
    }
    return null;
  };

  const activeSegment = findActiveSegment();

  // Handle downloading transcript as text
  const handleDownloadTranscript = () => {
    // Create text content
    const textContent = segments
      .map((segment) => {
        const time = formatTimeForDownload(segment.start_time);
        return showTimestamps ? `[${time}] ${segment.text}` : segment.text;
      })
      .join("\n\n");

    // Create and trigger download
    const blob = new Blob([textContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcript.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Format time for download (HH:MM:SS)
  const formatTimeForDownload = (seconds) => {
    if (seconds === undefined || seconds === null) return "00:00:00";

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
          Transcript
        </h3>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowTimestamps(!showTimestamps)}
            className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            {showTimestamps ? "Hide Timestamps" : "Show Timestamps"}
          </button>
          <button
            onClick={handleDownloadTranscript}
            className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Download
          </button>
        </div>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search transcript..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
        />
      </div>

      <div className="max-h-[500px] overflow-y-auto pr-2">
        {filteredSegments.map((segment, index) => (
          <TranscriptSegment
            key={index}
            segment={segment}
            isActive={
              activeSegment && activeSegment.start_time === segment.start_time
            }
            showTimestamps={showTimestamps}
            onClick={onSegmentClick}
          />
        ))}
      </div>
    </div>
  );
};

export default TranscriptList;
