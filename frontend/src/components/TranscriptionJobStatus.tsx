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
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-3/4 rounded bg-white/10" />
          <div className="h-4 w-full rounded bg-white/10" />
        </div>
      );
    }

    if (jobsQuery.isError) {
      return (
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-destructive text-sm">
          Failed to load transcription status. Please try again later.
        </div>
      );
    }

    if (!activeJob) {
      return null;
    }

    return (
      <div className="space-y-4">
        {activeJob.status === "failed" && (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-destructive">
            <p className="font-semibold">Transcription failed</p>
            <p className="mt-2 text-sm">
              {getErrorMessage(activeJob.error_details)}
            </p>
          </div>
        )}

        {(activeJob.status === "pending" ||
          activeJob.status === "processing") && (
          <div className="rounded-2xl border border-sky-400/20 bg-sky-400/10 p-4 text-sky-100">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 h-5 w-5 animate-spin rounded-full border-2 border-sky-200/30 border-t-sky-100" />
              <div>
                <p className="font-semibold">
                  {activeJob.status === "pending"
                    ? "Queued for transcription"
                    : "Transcribing video"}
                </p>
                <p className="mt-2 text-sky-100/80 text-sm">
                  This can take a while for longer footage, but the page will
                  keep updating automatically.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeJob.status === "failed" && (
          <button
            className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate(activeJob.id)}
            type="button"
          >
            {retryMutation.isPending ? "Retrying..." : "Retry transcription"}
          </button>
        )}
      </div>
    );
  }

  return (
    <section className="panel p-5">
      <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
        Pipeline
      </p>
      <h2 className="mt-2 font-semibold text-foreground text-xl">
        Transcription status
      </h2>
      <div className="mt-4">{renderStatusContent()}</div>
    </section>
  );
}
