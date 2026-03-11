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
      return <div className="h-4 w-3/4 animate-pulse rounded bg-white/10" />;
    }

    if (jobsQuery.isError) {
      return (
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-destructive text-sm">
          Failed to load summarization status.
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
            <p className="font-semibold">Summary generation failed</p>
            <p className="mt-2 text-sm">
              {getErrorMessage(activeJob.error_details)}
            </p>
          </div>
        )}

        {(activeJob.status === "pending" ||
          activeJob.status === "processing") && (
          <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4 text-amber-100">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 h-5 w-5 animate-spin rounded-full border-2 border-amber-100/30 border-t-amber-100" />
              <div>
                <p className="font-semibold">
                  {activeJob.status === "pending"
                    ? "Queued for summary"
                    : "Generating summary"}
                </p>
                <p className="mt-2 text-amber-100/80 text-sm">
                  The summarizer is reading the transcript and preparing the key
                  takeaways.
                </p>
              </div>
            </div>
          </div>
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
        Summary status
      </h2>
      <div className="mt-4">{renderStatusContent()}</div>
    </section>
  );
}
