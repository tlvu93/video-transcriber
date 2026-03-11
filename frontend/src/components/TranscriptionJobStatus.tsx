import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTranscriptionJobs,
  retryTranscriptionJob,
} from "../api/videoService";

interface TranscriptionJobStatusProps {
  onJobRetried?: () => void;
  videoId: string;
}

function getErrorMessage(
  errorDetails: Record<string, unknown> | null | undefined
): string {
  const message = errorDetails?.error;
  return typeof message === "string"
    ? message
    : "An unknown error occurred during transcription.";
}

export default function TranscriptionJobStatus({
  videoId,
  onJobRetried,
}: TranscriptionJobStatusProps) {
  const queryClient = useQueryClient();
  const jobsQuery = useQuery({
    queryKey: ["transcriptionJobs", videoId],
    queryFn: () => fetchTranscriptionJobs(videoId),
    enabled: Boolean(videoId),
    select: (jobs) =>
      [...jobs].sort(
        (left, right) =>
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime()
      ),
  });
  const retryMutation = useMutation({
    mutationFn: retryTranscriptionJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["transcriptionJobs", videoId],
      });
      onJobRetried?.();
    },
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
          <div className="mb-2 h-4 w-full rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      );
    }

    if (jobsQuery.isError) {
      return (
        <div className="rounded border-red-500 border-l-4 bg-red-100 p-2 text-red-700 dark:bg-red-900/30 dark:text-red-400">
          <p>Failed to load job status. Please try again later.</p>
        </div>
      );
    }

    if (!activeJob) {
      return null;
    }

    return (
      <div className="mb-2">
        {activeJob.status === "failed" && (
          <div className="mb-3 rounded border-red-500 border-l-4 bg-red-100 p-3 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            <p className="font-semibold">Transcription Failed</p>
            <p className="mt-1 text-sm">
              {getErrorMessage(activeJob.error_details)}
            </p>
          </div>
        )}

        {(activeJob.status === "pending" ||
          activeJob.status === "processing") && (
          <div className="mb-3 flex items-center rounded border-blue-500 border-l-4 bg-blue-50 p-3 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
            <div className="mr-3 h-5 w-5 animate-spin rounded-full border-blue-500 border-t-2 border-b-2" />
            <div>
              <p className="font-semibold">
                {activeJob.status === "pending"
                  ? "Waiting to start..."
                  : "Transcribing Video..."}
              </p>
              <p className="mt-1 text-sm opacity-80">
                This may take a while depending on the video length.
              </p>
            </div>
          </div>
        )}

        {activeJob.status === "failed" && (
          <button
            className="rounded bg-blue-500 px-4 py-2 font-semibold text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate(activeJob.id)}
            type="button"
          >
            {retryMutation.isPending ? (
              <>
                <span className="mr-2 inline-block animate-spin">⟳</span>
                Retrying...
              </>
            ) : (
              "Retry Transcription"
            )}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
      <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
        Transcription Status
      </h2>
      {renderStatusContent()}
    </div>
  );
}
