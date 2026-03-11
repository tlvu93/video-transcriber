import { useQuery } from "@tanstack/react-query";
import { fetchSummarizationJobs } from "../api/videoService";

interface SummarizationJobStatusProps {
  transcriptId: string;
}

function getErrorMessage(
  errorDetails: Record<string, unknown> | null | undefined
): string {
  const message = errorDetails?.error;
  return typeof message === "string" ? message : "Unknown error occurred.";
}

export default function SummarizationJobStatus({
  transcriptId,
}: SummarizationJobStatusProps) {
  const jobsQuery = useQuery({
    queryKey: ["summarizationJobs", transcriptId],
    queryFn: () => fetchSummarizationJobs(transcriptId),
    enabled: Boolean(transcriptId),
    select: (jobs) =>
      [...jobs].sort(
        (left, right) =>
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime()
      ),
  });
  const jobs = jobsQuery.data ?? [];

  if (!jobsQuery.isPending && jobs.length === 0 && !jobsQuery.isError) {
    return null;
  }

  const activeJob = jobs[0] ?? null;

  if (activeJob && activeJob.status === "completed") {
    return null;
  }

  function renderStatusContent() {
    if (jobsQuery.isPending && !activeJob) {
      return (
        <div className="animate-pulse">
          <div className="mb-2 h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      );
    }

    if (jobsQuery.isError) {
      return (
        <div className="text-red-500 text-sm">Failed to load job status.</div>
      );
    }

    if (!activeJob) {
      return null;
    }

    return (
      <div className="mb-2">
        {activeJob.status === "failed" && (
          <div className="mb-3 rounded border-red-500 border-l-4 bg-red-100 p-3 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            <p className="font-semibold">Summarization Failed</p>
            <p className="mt-1 text-sm">
              {getErrorMessage(activeJob.error_details)}
            </p>
          </div>
        )}

        {(activeJob.status === "pending" ||
          activeJob.status === "processing") && (
          <div className="mb-3 flex items-center rounded border-purple-500 border-l-4 bg-purple-50 p-3 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400">
            <div className="mr-3 h-5 w-5 animate-spin rounded-full border-purple-500 border-t-2 border-b-2" />
            <div>
              <p className="font-semibold">
                {activeJob.status === "pending"
                  ? "Waiting for Summarizer..."
                  : "Generating Summary with Ollama..."}
              </p>
              <p className="mt-1 text-sm opacity-80">
                Using local AI model to read the transcript.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
      <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
        Summarization Status
      </h2>
      {renderStatusContent()}
    </div>
  );
}
