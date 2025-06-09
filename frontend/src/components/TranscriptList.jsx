import { useState } from "react";
import TranscriptSegment from "./TranscriptSegment";

const TranscriptList = ({ transcript, currentTime, onSegmentClick }) => {
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeaker, setShowSpeaker] = useState(true); // New state for speaker visibility
  const [menuOpen, setMenuOpen] = useState(false); // New state for menu visibility
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
    const textContent = segments
      .map((segment) => {
        let line = "";
        if (showTimestamps && showSpeaker && segment.speaker) {
          line = `[${formatTimeForDownload(segment.start_time)}] ${
            segment.speaker
          }: ${segment.text}`;
        } else if (showTimestamps) {
          line = `[${formatTimeForDownload(segment.start_time)}] ${
            segment.text
          }`;
        } else if (showSpeaker && segment.speaker) {
          line = `${segment.speaker}: ${segment.text}`;
        } else {
          line = segment.text;
        }
        return line;
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
        <div className="relative inline-block text-left">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Menu
          </button>
          {menuOpen && (
            <div className="origin-top-right absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white dark:bg-gray-700 ring-1 ring-black ring-opacity-5 focus:outline-none z-10">
              <div
                className="py-1"
                role="menu"
                aria-orientation="vertical"
                aria-labelledby="options-menu"
              >
                <div className="px-4 py-2 text-sm text-gray-700 dark:text-gray-200 font-semibold">
                  Category Options
                </div>
                <button
                  onClick={() => {
                    setShowTimestamps(!showTimestamps);
                    // setMenuOpen(false); // Optionally close menu on selection
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  {showTimestamps ? "Hide Timestamps" : "Show Timestamps"}
                </button>
                <button
                  onClick={() => {
                    setShowSpeaker(!showSpeaker);
                    // setMenuOpen(false); // Optionally close menu on selection
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  {showSpeaker ? "Hide Speaker" : "Show Speaker"}
                </button>
                <hr className="my-1 border-gray-200 dark:border-gray-600" />
                <button
                  onClick={() => {
                    handleDownloadTranscript();
                    setMenuOpen(false); // Close menu after action
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  Download Transcript
                </button>
              </div>
            </div>
          )}
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
            showSpeaker={showSpeaker} // Pass showSpeaker prop
            onClick={onSegmentClick}
          />
        ))}
      </div>
    </div>
  );
};

export default TranscriptList;
