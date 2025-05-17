import { useState, useEffect, Fragment } from "react";
import { fetchSummariesByTranscriptId } from "../api/videoService";

// Function to format summary content for better readability
const formatSummaryContent = (content) => {
  if (!content) return null;

  // Check if content has numbered points (e.g., "1.", "2.", etc.)
  const hasNumberedPoints = /\d+\.\s/.test(content);

  // Split content by various potential delimiters
  let paragraphs = [];

  if (hasNumberedPoints) {
    // For numbered lists, split by number pattern
    const numberPattern = /(\d+\.\s+)/g;
    const parts = content.split(numberPattern);

    // Process the parts into numbered items
    for (let i = 1; i < parts.length; i += 2) {
      if (i + 1 < parts.length) {
        const number = parts[i];
        const text = parts[i + 1];

        // Process sub-points if they exist (e.g., "- Point" or "* Point")
        const subPoints = text.split(/\n\s*[-*]\s+/);

        if (subPoints.length > 1) {
          // First part is the main point
          paragraphs.push({
            type: "numbered",
            number: number.trim(),
            text: subPoints[0].trim(),
            subPoints: subPoints
              .slice(1)
              .map((sp) => sp.trim())
              .filter((sp) => sp),
          });
        } else {
          paragraphs.push({
            type: "numbered",
            number: number.trim(),
            text: text.trim(),
            subPoints: [],
          });
        }
      }
    }

    // If there's content before the first number, add it as an intro paragraph
    if (parts[0].trim()) {
      paragraphs.unshift({
        type: "paragraph",
        text: parts[0].trim(),
      });
    }
  } else {
    // For regular content, split by double newlines or other common separators
    paragraphs = content
      .split(/\n\n+|\.\s+(?=[A-Z])/)
      .map((p) => p.trim())
      .filter((p) => p)
      .map((p) => ({ type: "paragraph", text: p }));
  }

  // Render the formatted content
  return (
    <div className="text-gray-600 dark:text-gray-300">
      {paragraphs.map((para, index) => {
        if (para.type === "numbered") {
          return (
            <div key={index} className="mb-3">
              <div className="flex">
                <div className="font-bold mr-2">{para.number}</div>
                <div className="font-semibold">{para.text}</div>
              </div>
              {para.subPoints.length > 0 && (
                <ul className="list-disc pl-10 mt-1 space-y-1">
                  {para.subPoints.map((subPoint, subIndex) => (
                    <li key={`${index}-${subIndex}`}>{subPoint}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        } else {
          return (
            <p key={index} className="mb-3">
              {para.text}
            </p>
          );
        }
      })}
    </div>
  );
};

const VideoSummary = ({ transcript }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSummary = async () => {
      if (!transcript || !transcript.id) return;

      try {
        setLoading(true);
        const summaries = await fetchSummariesByTranscriptId(transcript.id);

        if (summaries && summaries.length > 0) {
          setSummary(summaries[0]); // Use the first summary
        } else {
          setSummary(null);
        }

        setLoading(false);
      } catch (err) {
        console.error("Error fetching summary:", err);
        setError("Failed to load summary. Please try again later.");
        setLoading(false);
      }
    };

    fetchSummary();
  }, [transcript]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
        <h2 className="text-xl font-semibold mb-2 text-gray-800 dark:text-white">
          Summary
        </h2>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
        <h2 className="text-xl font-semibold mb-2 text-gray-800 dark:text-white">
          Summary
        </h2>
        <div className="bg-red-100 dark:bg-red-900/30 border-l-4 border-red-500 text-red-700 dark:text-red-400 p-2 rounded">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
        <h2 className="text-xl font-semibold mb-2 text-gray-800 dark:text-white">
          Summary
        </h2>
        <p className="text-gray-500 dark:text-gray-400 italic">
          No summary available for this video.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
      <h2 className="text-xl font-semibold mb-2 text-gray-800 dark:text-white">
        Summary
      </h2>
      <div className="prose dark:prose-invert max-w-none">
        {formatSummaryContent(summary.content)}
      </div>
    </div>
  );
};

export default VideoSummary;
