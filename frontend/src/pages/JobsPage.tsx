import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  cancelUnifiedJob,
  fetchJobAttempts,
  fetchUnifiedJobs,
  retryUnifiedJob,
} from "../api/videoService";
import { FeedbackPanel } from "../components/WorkspaceStates";
import { useUnifiedJobLiveUpdates } from "../hooks/useLiveUpdates";
import type { UnifiedJob } from "../types/domain";
import { formatRelativeDate } from "../utils/formatters";

function JobCard({
  isCancelling,
  isExpanded,
  isRetrying,
  job,
  onCancel,
  onRetry,
  onToggle,
}: {
  isCancelling: boolean;
  isExpanded: boolean;
  isRetrying: boolean;
  job: UnifiedJob;
  onCancel: () => void;
  onRetry: () => void;
  onToggle: () => void;
}) {
  const attemptsQuery = useQuery({
    queryKey: ["jobAttempts", job.id],
    queryFn: () => fetchJobAttempts(job.id),
    enabled: isExpanded,
  });
  const progressPercent =
    job.progress === null || job.progress === undefined
      ? null
      : Math.round(Math.max(0, Math.min(job.progress, 1)) * 100);
  const canCancel =
    job.status === "pending" ||
    job.status === "processing" ||
    job.status === "cancel_requested";
  const canRetry = job.status === "failed" || job.status === "cancelled";

  return (
    <section className="panel overflow-hidden p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-semibold text-primary text-xs uppercase tracking-[0.18em]">
              {job.job_type}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-muted-foreground text-xs">
              {job.status}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-muted-foreground text-xs">
              {job.subject_type}: {job.subject_id.slice(0, 8)}
            </span>
          </div>
          <h2 className="mt-4 font-semibold text-foreground text-xl tracking-tight">
            Unified job {job.id.slice(0, 8)}
          </h2>
          <p className="mt-2 text-muted-foreground text-sm">
            Legacy source: {job.legacy_job_table} / {job.legacy_job_id.slice(0, 8)}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-4 lg:min-w-[26rem]">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Attempts
            </p>
            <p className="mt-2 text-foreground text-sm">{job.attempt_count}</p>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Worker
            </p>
            <p className="mt-2 truncate text-foreground text-sm">
              {job.worker_id ?? "Idle"}
            </p>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Created
            </p>
            <p className="mt-2 text-foreground text-sm">
              {formatRelativeDate(job.created_at)}
            </p>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Progress
            </p>
            {progressPercent === null ? (
              <p className="mt-2 text-foreground text-sm">Waiting</p>
            ) : (
              <>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <p className="mt-2 text-foreground text-sm">{progressPercent}%</p>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {job.payload && Object.keys(job.payload).length > 0 ? (
            Object.entries(job.payload).map(([key, value]) => (
              <span
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1"
                key={key}
              >
                {key}: {String(value)}
              </span>
            ))
          ) : (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
              No extra payload
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {canCancel ? (
            <button
              className="rounded-full border border-warning/30 bg-warning/10 px-4 py-2 font-medium text-sm text-warning transition hover:bg-warning/15 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isCancelling || job.status === "cancel_requested"}
              onClick={onCancel}
              type="button"
            >
              {job.status === "cancel_requested"
                ? "Cancel requested"
                : isCancelling
                  ? "Cancelling..."
                  : "Cancel job"}
            </button>
          ) : null}
          {canRetry ? (
            <button
              className="rounded-full border border-primary/30 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isRetrying}
              onClick={onRetry}
              type="button"
            >
              {isRetrying ? "Retrying..." : "Retry job"}
            </button>
          ) : null}
          <button
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 font-medium text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
            onClick={onToggle}
            type="button"
          >
            {isExpanded ? "Hide attempts" : "Show attempts"}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          {attemptsQuery.isPending ? (
            <p className="text-muted-foreground text-sm">Loading attempts...</p>
          ) : attemptsQuery.isError ? (
            <p className="text-sm text-warning">Failed to load attempts.</p>
          ) : attemptsQuery.data && attemptsQuery.data.length > 0 ? (
            <div className="space-y-3">
              {attemptsQuery.data.map((attempt) => (
                <div
                  className="rounded-2xl border border-white/8 bg-background/40 px-4 py-3"
                  key={attempt.id}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-foreground">
                      Attempt {attempt.attempt_number}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-muted-foreground">
                      {attempt.status}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-muted-foreground">
                      {attempt.worker_id ?? "No worker"}
                    </span>
                  </div>
                  <p className="mt-2 text-muted-foreground text-xs">
                    Started {formatRelativeDate(attempt.started_at)}
                    {attempt.completed_at
                      ? ` · completed ${formatRelativeDate(attempt.completed_at)}`
                      : ""}
                  </p>
                  {attempt.error_details?.error ? (
                    <p className="mt-3 text-sm text-warning">
                      {attempt.error_details.error}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No attempts recorded yet.</p>
          )}
        </div>
      )}
    </section>
  );
}


export default function JobsPage() {
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const [jobTypeFilter, setJobTypeFilter] = useState<
    "all" | "summarization" | "transcription" | "translation"
  >("all");
  const [statusFilter, setStatusFilter] = useState<
    | "all"
    | "cancel_requested"
    | "cancelled"
    | "completed"
    | "failed"
    | "pending"
    | "processing"
  >("all");
  useUnifiedJobLiveUpdates();

  const invalidateJobs = () => {
    queryClient.invalidateQueries({ queryKey: ["unifiedJobs"] });
  };

  const cancelMutation = useMutation({
    mutationFn: cancelUnifiedJob,
    onSuccess: invalidateJobs,
  });

  const retryMutation = useMutation({
    mutationFn: retryUnifiedJob,
    onSuccess: invalidateJobs,
  });

  const jobsQuery = useQuery({
    queryKey: ["unifiedJobs", jobTypeFilter, statusFilter],
    queryFn: () =>
      fetchUnifiedJobs({
        jobType: jobTypeFilter === "all" ? undefined : jobTypeFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
      }),
  });

  if (jobsQuery.isPending) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <p className="text-muted-foreground">Loading job dashboard...</p>
      </div>
    );
  }

  if (jobsQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <FeedbackPanel
          description="The orchestration dashboard could not be loaded right now."
          eyebrow="Error"
          title="Failed to load jobs"
          tone="error"
        />
      </div>
    );
  }

  const jobs = jobsQuery.data?.items ?? [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link
            className="inline-flex items-center gap-2 text-muted-foreground text-sm transition hover:text-foreground"
            to="/"
          >
            Back to library
          </Link>
          <h1 className="mt-4 font-semibold text-3xl text-foreground tracking-tight sm:text-4xl">
            Job orchestration
          </h1>
          <p className="mt-2 text-muted-foreground">
            Canonical view over transcription, summarization, and translation jobs.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <select
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm"
            onChange={(event) =>
              setJobTypeFilter(
                event.target.value as
                  | "all"
                  | "summarization"
                  | "transcription"
                  | "translation"
              )
            }
            value={jobTypeFilter}
          >
            <option value="all">All job types</option>
            <option value="transcription">Transcription</option>
            <option value="summarization">Summarization</option>
            <option value="translation">Translation</option>
          </select>
          <select
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm"
            onChange={(event) =>
              setStatusFilter(
                event.target.value as
                  | "cancel_requested"
                  | "cancelled"
                  | "all"
                  | "completed"
                  | "failed"
                  | "pending"
                  | "processing"
              )
            }
            value={statusFilter}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="cancel_requested">Cancel requested</option>
            <option value="cancelled">Cancelled</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      <div className="space-y-4">
        {jobs.length === 0 ? (
          <div className="panel p-6 text-muted-foreground">
            No unified jobs match the current filters.
          </div>
        ) : (
          jobs.map((job) => (
            <JobCard
              isCancelling={
                cancelMutation.isPending && cancelMutation.variables === job.id
              }
              isExpanded={expandedJobId === job.id}
              isRetrying={retryMutation.isPending && retryMutation.variables === job.id}
              job={job}
              key={job.id}
              onCancel={() => cancelMutation.mutate(job.id)}
              onRetry={() => retryMutation.mutate(job.id)}
              onToggle={() =>
                setExpandedJobId((current) => (current === job.id ? null : job.id))
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
