import { useState, useEffect } from "react";
import { retryTranscriptionJob } from "../api/videoService";

const TranscriptionJobStatus = ({ videoId, onJobRetried }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(false);

  // Fetch transcription jobs for the video
  useEffect(() => {
    const fetchJobs = async () => {
      if (!videoId) return;

      try {
        setLoading(true);
        // This is a placeholder until the API endpoint is implemented
        // In a real implementation, you would fetch the actual jobs from the API
        const response = await fetch(`/api/videos/${videoId}`);
        const videoData = await response.json();

        // Check if the video status is "error" which indicates a failed job
        if (videoData.status === "error") {
          // Create a mock job object since we don't have a direct API to fetch jobs by video ID
          setJobs([
            {
              id: "unknown", // We don't know the actual job ID
              video_id: videoId,
              status: "failed",
              error_details: {
                error:
                  "Transcription failed. The job may have been interrupted.",
              },
            },
          ]);
        } else {
          setJobs([]);
        }

        setLoading(false);
      } catch (err) {
        console.error("Error fetching transcription jobs:", err);
        setError("Failed to load job status. Please try again later.");
        setLoading(false);
      }
    };

    fetchJobs();
  }, [videoId]);

  // Handle retry button click
  const handleRetry = async (jobId) => {
    try {
      setRetrying(true);

      // If we don't have a real job ID, we need to create a new transcription job
      if (jobId === "unknown") {
        // Create a new transcription job for the video
        const response = await fetch(`/api/transcription-jobs/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ video_id: videoId }),
        });

        if (!response.ok) {
          throw new Error("Failed to create new transcription job");
        }

        // Update the video status to pending
        await fetch(`/api/videos/${videoId}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status: "pending" }),
        });
      } else {
        // Retry the existing job
        await retryTranscriptionJob(jobId);
      }

      // Clear the jobs list and notify parent component
      setJobs([]);
      if (onJobRetried) {
        onJobRetried();
      }

      setRetrying(false);
    } catch (err) {
      console.error("Error retrying transcription job:", err);
      setError("Failed to retry transcription. Please try again later.");
      setRetrying(false);
    }
  };

  // If no failed jobs, don't render anything
  if (!loading && jobs.length === 0 && !error) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4">
      <h2 className="text-xl font-semibold mb-2 text-gray-800 dark:text-white">
        Transcription Status
      </h2>

      {loading ? (
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2"></div>
        </div>
      ) : error ? (
        <div className="bg-red-100 dark:bg-red-900/30 border-l-4 border-red-500 text-red-700 dark:text-red-400 p-2 rounded">
          <p>{error}</p>
        </div>
      ) : (
        jobs.map((job) => (
          <div key={job.id} className="mb-4">
            {job.status === "failed" && (
              <div className="bg-red-100 dark:bg-red-900/30 border-l-4 border-red-500 text-red-700 dark:text-red-400 p-3 rounded mb-3">
                <p className="font-semibold">Transcription Failed</p>
                <p className="text-sm mt-1">
                  {job.error_details?.error ||
                    "An unknown error occurred during transcription."}
                </p>
              </div>
            )}

            <button
              onClick={() => handleRetry(job.id)}
              disabled={retrying}
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {retrying ? (
                <>
                  <span className="inline-block animate-spin mr-2">⟳</span>
                  Retrying...
                </>
              ) : (
                "Retry Transcription"
              )}
            </button>
          </div>
        ))
      )}
    </div>
  );
};

export default TranscriptionJobStatus;
