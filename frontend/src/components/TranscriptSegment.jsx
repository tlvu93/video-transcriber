const funnySpeakerNames = [
  "Captain Chatterbox",
  "Professor Ponder",
  "Duchess of Dialogue",
  "Sir Reginald Monologue",
  "The Oracle of Oratory",
  "Whispering Willow",
  "Baron Von Blabbermouth",
  "Countess Converse",
  "Agent Articulation",
  "Chancellor of Chit-Chat",
];

const getFunnyName = (speakerId) => {
  if (!speakerId || !speakerId.includes("_")) {
    return speakerId; // Return original if not in expected format
  }
  const parts = speakerId.split("_");
  const numStr = parts[parts.length - 1];
  const num = parseInt(numStr, 10);

  if (isNaN(num)) {
    return speakerId; // Return original if number parsing fails
  }

  return funnySpeakerNames[num % funnySpeakerNames.length];
};

const TranscriptSegment = ({ segment, isActive, showTimestamps, showSpeaker, onClick }) => {
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
    speaker: segment.speaker || null,
  };

  // Generate speaker color based on speaker ID
  const getSpeakerColor = (speaker) => {
    if (!speaker) return null;

    const colors = [
      "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
      "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
      "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
      "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
      "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    ];

    // Use speaker ID to consistently assign colors
    const speakerNum = parseInt(speaker.replace(/\D/g, "")) || 0;
    return colors[speakerNum % colors.length];
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
      <div className="flex items-start gap-2">
        {showTimestamps && (
          <span className="text-xs font-mono text-gray-500 dark:text-gray-400 flex-shrink-0">
            [{formatTime(safeSegment.start_time)}]
          </span>
        )}
        {showSpeaker && safeSegment.speaker && (
          <span
            className={`text-xs px-2 py-1 rounded-full font-medium flex-shrink-0 ${getSpeakerColor(
              safeSegment.speaker
            )}`}
          >
            {getFunnyName(safeSegment.speaker)}
          </span>
        )}
        <span className="text-gray-800 dark:text-gray-200 flex-1">
          {safeSegment.text}
        </span>
      </div>
    </div>
  );
};

export default TranscriptSegment;
