import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  createSummarizationJob,
  fetchSummariesByTranscriptId,
  fetchSummarizationJobs,
} from "../api/videoService";
import type { SummarizationJob, Summary } from "../types/domain";
import { formatRelativeDate } from "../utils/formatters";
import { sortByNewest } from "../utils/transcript";
import { SummaryPanelSkeleton } from "./WorkspaceStates";

const NUMBERED_POINT_PATTERN = /\d+\.\s/;
const NUMBER_SPLIT_PATTERN = /(\d+\.\s+)/g;
const SENTENCE_SPLIT_PATTERN = /\n\n+|\.\s+(?=[A-Z])/;
const SUBPOINT_SPLIT_PATTERN = /\n\s*[-*]\s+/;

type SummaryParagraph =
  | {
      type: "numbered";
      text: string;
      number: string;
      subPoints: string[];
    }
  | {
      type: "paragraph";
      text: string;
    };

function formatSummaryContent(content: string | undefined): ReactNode {
  if (!content) {
    return null;
  }

  const hasNumberedPoints = NUMBERED_POINT_PATTERN.test(content);

  let paragraphs: SummaryParagraph[] = [];

  if (hasNumberedPoints) {
    const parts = content.split(NUMBER_SPLIT_PATTERN);

    for (let i = 1; i < parts.length; i += 2) {
      if (i + 1 < parts.length) {
        const number = parts[i];
        const text = parts[i + 1];
        if (!(number && text)) {
          continue;
        }

        const subPoints = text.split(SUBPOINT_SPLIT_PATTERN);

        if (subPoints.length > 1) {
          const mainPoint = subPoints[0] ?? text;

          paragraphs.push({
            type: "numbered",
            number: number.trim(),
            text: mainPoint.trim(),
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

    const leadParagraph = parts[0] ?? "";

    if (leadParagraph.trim()) {
      paragraphs.unshift({
        type: "paragraph",
        text: leadParagraph.trim(),
      });
    }
  } else {
    paragraphs = content
      .split(SENTENCE_SPLIT_PATTERN)
      .map((paragraph) => paragraph.trim())
      .filter((paragraph) => paragraph)
      .map((paragraph) => ({ type: "paragraph" as const, text: paragraph }));
  }

  return (
    <div className="space-y-4 text-slate-200 text-sm leading-7">
      {paragraphs.map((para) => {
        const paragraphKey =
          para.type === "numbered" ? `${para.number}-${para.text}` : para.text;

        if (para.type === "numbered") {
          return (
            <div
              className="rounded-2xl border border-white/8 bg-white/5 p-4"
              key={paragraphKey}
            >
              <div className="flex gap-3">
                <div className="font-semibold text-primary">{para.number}</div>
                <div className="font-medium text-foreground">{para.text}</div>
              </div>
              {para.subPoints.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-10 text-muted-foreground">
                  {para.subPoints.map((subPoint) => (
                    <li key={`${paragraphKey}-${subPoint}`}>{subPoint}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        }

        return (
          <p className="text-muted-foreground" key={paragraphKey}>
            {para.text}
          </p>
        );
      })}
    </div>
  );
}

interface VideoSummaryProps {
  transcriptId: string;
}

function SparkleIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M12 3.75 13.37 8.63 18.25 10l-4.88 1.37L12 16.25l-1.37-4.88L5.75 10l4.88-1.37L12 3.75z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18 3.75 18.56 5.44 20.25 6l-1.69.56L18 8.25l-.56-1.69L15.75 6l1.69-.56L18 3.75zM18 15.75l.56 1.69 1.69.56-1.69.56L18 20.25l-.56-1.69-1.69-.56 1.69-.56L18 15.75z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M8.25 7.5V6A2.25 2.25 0 0110.5 3.75h7.5A2.25 2.25 0 0120.25 6v7.5A2.25 2.25 0 0118 15.75h-1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6 8.25h7.5A2.25 2.25 0 0115.75 10.5V18A2.25 2.25 0 0113.5 20.25H6A2.25 2.25 0 013.75 18v-7.5A2.25 2.25 0 016 8.25z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="m5.25 12.75 4.5 4.5 9-9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function RefreshIcon({ spinning = false }: { spinning?: boolean }) {
  return (
    <svg
      aria-hidden="true"
      className={`h-4 w-4 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M16.023 9.348h4.227V5.121M3.75 11.25a8.25 8.25 0 0114.091-5.825l2.409 2.409M7.977 14.652H3.75v4.227m16.5-6.729a8.25 8.25 0 01-14.091 5.825l-2.409-2.409"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function getLatestJob(jobs: SummarizationJob[]) {
  return (
    jobs.find(
      (job) => job.status === "pending" || job.status === "processing"
    ) ??
    jobs[0] ??
    null
  );
}

function getSummaryJobMessage(job: SummarizationJob | null) {
  if (!job) {
    return "A summary will appear here after the transcript has been processed.";
  }

  if (job.status === "pending") {
    return "The next summary run is queued and waiting for the worker to pick it up.";
  }

  if (job.status === "processing") {
    return "The summarizer is reading the transcript and drafting key takeaways now.";
  }

  if (job.status === "failed") {
    const message = job.error_details?.error;
    return typeof message === "string"
      ? message
      : "The last summary run failed. Try generating it again.";
  }

  return "The latest summary output is ready.";
}

export default function VideoSummary({ transcriptId }: VideoSummaryProps) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const summaryQuery = useQuery({
    queryKey: ["summaries", transcriptId],
    queryFn: () => fetchSummariesByTranscriptId(transcriptId),
    enabled: Boolean(transcriptId),
    select: sortByNewest,
  });
  const jobsQuery = useQuery({
    queryKey: ["summarizationJobs", transcriptId],
    queryFn: () => fetchSummarizationJobs(transcriptId),
    enabled: Boolean(transcriptId),
    select: sortByNewest,
  });
  const generateMutation = useMutation({
    mutationFn: () => createSummarizationJob(transcriptId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["summarizationJobs", transcriptId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["summaries", transcriptId],
      });
    },
  });
  const summaries = summaryQuery.data ?? [];
  const jobs = jobsQuery.data ?? [];
  const summary: Summary | null = summaries[0] ?? null;
  const latestJob = getLatestJob(jobs);
  const isGenerating =
    generateMutation.isPending ||
    latestJob?.status === "pending" ||
    latestJob?.status === "processing";
  const hasQueryError = summaryQuery.isError || jobsQuery.isError;
  const actionLabel = summary ? "Regenerate" : "Generate";
  let statusPill = "Ready";

  if (isGenerating) {
    statusPill = "Generating";
  } else if (latestJob?.status === "failed") {
    statusPill = "Needs attention";
  } else if (summary) {
    statusPill = `Updated ${formatRelativeDate(summary.created_at)}`;
  }

  let statusPillClassName = "border-white/10 bg-white/5 text-muted-foreground";

  if (latestJob?.status === "failed") {
    statusPillClassName =
      "border-destructive/20 bg-destructive/10 text-destructive";
  } else if (isGenerating) {
    statusPillClassName = "border-primary/20 bg-primary/10 text-primary";
  }

  useEffect(() => {
    if (!copied) {
      return;
    }

    const timeoutId = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  async function handleCopy(): Promise<void> {
    if (!summary?.content) {
      return;
    }

    await navigator.clipboard.writeText(summary.content);
    setCopied(true);
  }

  async function handleGenerate(): Promise<void> {
    if (!transcriptId || isGenerating) {
      return;
    }

    await generateMutation.mutateAsync();
  }

  if (summaryQuery.isPending && jobsQuery.isPending && !summary && !latestJob) {
    return <SummaryPanelSkeleton />;
  }

  if (hasQueryError) {
    return (
      <section className="panel overflow-hidden border-destructive/20 bg-destructive/10">
        <div className="border-destructive/20 border-b px-5 py-4">
          <p className="font-semibold text-destructive/80 text-xs uppercase tracking-[0.24em]">
            Summary
          </p>
          <h2 className="mt-2 font-semibold text-foreground text-xl">
            AI summary
          </h2>
        </div>
        <div className="p-5">
          <p className="text-destructive text-sm">
            Failed to load summary data. Please try again later.
          </p>
        </div>
      </section>
    );
  }

  let content: ReactNode;

  if (summary) {
    content = (
      <>
        {isGenerating && (
          <div className="mb-5 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-primary text-sm">
            A new summary is being generated. The latest saved version stays
            visible until the refresh completes.
          </div>
        )}

        {latestJob?.status === "failed" && (
          <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-destructive text-sm">
            {getSummaryJobMessage(latestJob)}
          </div>
        )}

        {formatSummaryContent(summary.content)}

        <div className="mt-5 flex flex-wrap items-center gap-2 text-muted-foreground text-sm">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            Saved {formatRelativeDate(summary.created_at)}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            Summary ID {summary.id.slice(0, 8)}
          </span>
        </div>
      </>
    );
  } else if (isGenerating) {
    content = (
      <div>
        <div className="mb-5 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-primary text-sm">
          {getSummaryJobMessage(latestJob)}
        </div>
        <div className="space-y-3">
          <div className="h-5 w-4/5 animate-pulse rounded bg-white/8" />
          <div className="h-5 w-full animate-pulse rounded bg-white/8" />
          <div className="h-5 w-5/6 animate-pulse rounded bg-white/8" />
        </div>
      </div>
    );
  } else if (latestJob?.status === "failed") {
    content = (
      <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-5">
        <p className="font-semibold text-destructive">Summary run failed</p>
        <p className="mt-3 text-destructive text-sm leading-6">
          {getSummaryJobMessage(latestJob)}
        </p>
      </div>
    );
  } else {
    content = (
      <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
          <SparkleIcon />
        </div>
        <h3 className="mt-4 font-semibold text-foreground text-lg">
          Ready when you are
        </h3>
        <p className="mt-3 text-muted-foreground leading-7">
          {getSummaryJobMessage(latestJob)}
        </p>
      </div>
    );
  }

  return (
    <section className="panel overflow-hidden">
      <div className="border-white/10 border-b px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
                <SparkleIcon />
              </div>
              <div>
                <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
                  Summary
                </p>
                <h2 className="mt-1 font-semibold text-foreground text-xl">
                  AI summary
                </h2>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 font-medium text-xs uppercase tracking-[0.18em] ${statusPillClassName}`}
            >
              {statusPill}
            </span>

            <button
              className="rounded-full border border-white/10 bg-white/5 px-3 py-2 font-medium text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!summary}
              onClick={() => {
                handleCopy().catch((error) => {
                  console.error("Failed to copy summary:", error);
                });
              }}
              type="button"
            >
              <span className="inline-flex items-center gap-2">
                {copied ? <CheckIcon /> : <CopyIcon />}
                {copied ? "Copied" : "Copy"}
              </span>
            </button>

            <button
              className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!transcriptId || isGenerating}
              onClick={() => {
                handleGenerate().catch((error) => {
                  console.error("Failed to generate summary:", error);
                });
              }}
              type="button"
            >
              <span className="inline-flex items-center gap-2">
                <RefreshIcon spinning={isGenerating} />
                {isGenerating ? "Generating..." : actionLabel}
              </span>
            </button>
          </div>
        </div>
      </div>

      <div className="p-5">{content}</div>
    </section>
  );
}
