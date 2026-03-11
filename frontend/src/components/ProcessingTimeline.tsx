import { useQuery } from "@tanstack/react-query";
import {
  fetchSummariesByTranscriptId,
  fetchSummarizationJobs,
  fetchTranscriptionJobs,
  fetchTranslatedTranscripts,
  fetchTranslationJobs,
} from "../api/videoService";
import type { JobStatus } from "../types/domain";
import {
  normalizeTranslatedTranscript,
  sortByNewest,
} from "../utils/transcript";

interface ProcessingTimelineProps {
  transcriptAvailable: boolean;
  transcriptId?: string | null;
  transcriptSegmentCount?: number;
  videoId: string;
  videoStatus?: string | null;
}

type StepState = "completed" | "failed" | "in-progress" | "pending";

interface TimelineStep {
  detail: string;
  error?: string;
  id: string;
  label: string;
  meta?: string;
  state: StepState;
}

function CheckCircleIcon() {
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
        d="M9.5 12.5 11 14l3.5-4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ClockIcon() {
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
        d="M12 7.5v4.5l3 1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AlertIcon() {
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
        d="M12 8.25v4.5m0 3h.008v.008H12v-.008z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4 animate-spin"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle
        className="opacity-20"
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-90"
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3"
      />
    </svg>
  );
}

function formatCount(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function getErrorMessage(error: Record<string, unknown> | null | undefined) {
  const message = error?.error;
  return typeof message === "string" ? message : null;
}

function getStateMeta(state: StepState) {
  switch (state) {
    case "completed":
      return {
        connectorClassName: "bg-emerald-400/60",
        iconClassName:
          "border-emerald-400/25 bg-emerald-400/15 text-emerald-200",
        labelClassName: "text-emerald-200",
      };
    case "failed":
      return {
        connectorClassName: "bg-red-400/40",
        iconClassName: "border-red-400/25 bg-red-400/15 text-red-200",
        labelClassName: "text-red-200",
      };
    case "in-progress":
      return {
        connectorClassName: "bg-primary/50",
        iconClassName: "border-primary/25 bg-primary/15 text-primary",
        labelClassName: "text-primary",
      };
    default:
      return {
        connectorClassName: "bg-white/8",
        iconClassName: "border-white/10 bg-white/5 text-muted-foreground",
        labelClassName: "text-muted-foreground",
      };
  }
}

function StatusIcon({ state }: { state: StepState }) {
  if (state === "completed") {
    return <CheckCircleIcon />;
  }

  if (state === "failed") {
    return <AlertIcon />;
  }

  if (state === "in-progress") {
    return <SpinnerIcon />;
  }

  return <ClockIcon />;
}

function getLatestJob<T extends { status: JobStatus }>(jobs: T[]) {
  return (
    jobs.find(
      (job) => job.status === "pending" || job.status === "processing"
    ) ??
    jobs[0] ??
    null
  );
}

function getInProgressLabel(status: JobStatus | undefined | null) {
  return status === "pending" ? "Queued" : "Running";
}

function getTranslationLabel(language: string | undefined | null) {
  if (!language) {
    return "translation";
  }

  return language.toUpperCase();
}

export default function ProcessingTimeline({
  transcriptAvailable,
  transcriptId,
  transcriptSegmentCount = 0,
  videoId,
  videoStatus,
}: ProcessingTimelineProps) {
  const transcriptionJobsQuery = useQuery({
    queryKey: ["transcriptionJobs", videoId],
    queryFn: () => fetchTranscriptionJobs(videoId),
    enabled: Boolean(videoId),
    select: sortByNewest,
  });
  const summarizationJobsQuery = useQuery({
    queryKey: ["summarizationJobs", transcriptId],
    queryFn: () =>
      transcriptId ? fetchSummarizationJobs(transcriptId) : Promise.resolve([]),
    enabled: Boolean(transcriptId),
    select: sortByNewest,
  });
  const summariesQuery = useQuery({
    queryKey: ["summaries", transcriptId],
    queryFn: () =>
      transcriptId
        ? fetchSummariesByTranscriptId(transcriptId)
        : Promise.resolve([]),
    enabled: Boolean(transcriptId),
    select: sortByNewest,
  });
  const translationJobsQuery = useQuery({
    queryKey: ["translationJobs", transcriptId],
    queryFn: () =>
      transcriptId ? fetchTranslationJobs(transcriptId) : Promise.resolve([]),
    enabled: Boolean(transcriptId),
    select: sortByNewest,
  });
  const translationsQuery = useQuery({
    queryKey: ["translations", transcriptId],
    queryFn: async () => {
      if (!transcriptId) {
        return [];
      }

      const translations = await fetchTranslatedTranscripts(transcriptId);
      return translations
        .map((translation) => normalizeTranslatedTranscript(translation))
        .filter((translation): translation is NonNullable<typeof translation> =>
          Boolean(translation)
        );
    },
    enabled: Boolean(transcriptId),
  });

  const transcriptionJobs = transcriptionJobsQuery.data ?? [];
  const summarizationJobs = summarizationJobsQuery.data ?? [];
  const summaries = summariesQuery.data ?? [];
  const translationJobs = translationJobsQuery.data ?? [];
  const translations = translationsQuery.data ?? [];
  const latestTranscriptionJob = getLatestJob(transcriptionJobs);
  const latestSummarizationJob = getLatestJob(summarizationJobs);
  const latestTranslationJob = getLatestJob(translationJobs);
  const completedTranslations = translations.length;
  const activeTranslationJob =
    translationJobs.find(
      (job) => job.status === "pending" || job.status === "processing"
    ) ?? null;
  const videoFailed =
    videoStatus?.toLowerCase() === "error" ||
    videoStatus?.toLowerCase() === "failed";
  let transcriptStep: TimelineStep;

  if (transcriptAvailable) {
    transcriptStep = {
      id: "transcript",
      label: "Transcript",
      detail: "Transcript is ready for search, editing, and export.",
      meta:
        transcriptSegmentCount > 0
          ? formatCount(transcriptSegmentCount, "segment")
          : undefined,
      state: "completed",
    };
  } else if (latestTranscriptionJob?.status === "failed" || videoFailed) {
    transcriptStep = {
      id: "transcript",
      label: "Transcript",
      detail:
        "Transcription needs attention before the workspace can continue.",
      error:
        getErrorMessage(latestTranscriptionJob?.error_details) ??
        "The transcription worker reported a failure.",
      state: "failed",
    };
  } else if (
    latestTranscriptionJob?.status === "pending" ||
    latestTranscriptionJob?.status === "processing" ||
    videoStatus?.toLowerCase() === "pending" ||
    videoStatus?.toLowerCase() === "processing"
  ) {
    transcriptStep = {
      id: "transcript",
      label: "Transcript",
      detail:
        latestTranscriptionJob?.status === "pending"
          ? "Queued and waiting for a transcription worker."
          : "Audio is being processed into editable transcript segments.",
      meta: getInProgressLabel(latestTranscriptionJob?.status ?? "processing"),
      state: "in-progress",
    };
  } else {
    transcriptStep = {
      id: "transcript",
      label: "Transcript",
      detail: "A transcript will appear here once processing starts.",
      state: "pending",
    };
  }

  let summaryStep: TimelineStep;

  if (summaries.length > 0) {
    summaryStep = {
      id: "summary",
      label: "AI Summary",
      detail: "The AI summary is ready in the workspace below the player.",
      meta: formatCount(summaries.length, "summary", "summaries"),
      state: "completed",
    };
  } else if (latestSummarizationJob?.status === "failed") {
    summaryStep = {
      id: "summary",
      label: "AI Summary",
      detail: "Summary generation stopped before it could finish.",
      error:
        getErrorMessage(latestSummarizationJob.error_details) ??
        "The summarization worker reported a failure.",
      state: "failed",
    };
  } else if (
    latestSummarizationJob?.status === "pending" ||
    latestSummarizationJob?.status === "processing"
  ) {
    summaryStep = {
      id: "summary",
      label: "AI Summary",
      detail:
        latestSummarizationJob.status === "pending"
          ? "Queued and waiting for the transcript to be picked up."
          : "The summarizer is extracting the key takeaways now.",
      meta: getInProgressLabel(latestSummarizationJob.status),
      state: "in-progress",
    };
  } else if (transcriptAvailable) {
    summaryStep = {
      id: "summary",
      label: "AI Summary",
      detail: "Ready to generate once the summary job is requested.",
      state: "pending",
    };
  } else {
    summaryStep = {
      id: "summary",
      label: "AI Summary",
      detail: "Waiting for the transcript before summary generation can begin.",
      state: "pending",
    };
  }

  let translationStep: TimelineStep;

  if (completedTranslations > 0) {
    translationStep = {
      id: "translations",
      label: "Translations",
      detail:
        "Translated transcripts are available directly from the transcript panel.",
      meta: formatCount(completedTranslations, "language"),
      state: "completed",
    };
  } else if (latestTranslationJob?.status === "failed") {
    translationStep = {
      id: "translations",
      label: "Translations",
      detail:
        "The latest translation request failed before a transcript was saved.",
      error:
        getErrorMessage(latestTranslationJob.error_details) ??
        "The translation worker reported a failure.",
      state: "failed",
    };
  } else if (activeTranslationJob) {
    translationStep = {
      id: "translations",
      label: "Translations",
      detail: `Preparing the ${getTranslationLabel(
        activeTranslationJob.target_language
      )} translation now.`,
      meta: getInProgressLabel(activeTranslationJob.status),
      state: "in-progress",
    };
  } else if (transcriptAvailable) {
    translationStep = {
      id: "translations",
      label: "Translations",
      detail:
        "Request a language from the transcript panel whenever you need one.",
      state: "pending",
    };
  } else {
    translationStep = {
      id: "translations",
      label: "Translations",
      detail:
        "Translation becomes available after the original transcript is ready.",
      state: "pending",
    };
  }

  const steps: TimelineStep[] = [
    {
      id: "ingest",
      label: "Ingested",
      detail: "Video uploaded and attached to a live processing workspace.",
      state: "completed",
    },
    transcriptStep,
    summaryStep,
    translationStep,
  ];

  return (
    <section className="panel overflow-hidden">
      <div className="border-white/10 border-b px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
              Pipeline
            </p>
            <h2 className="mt-2 font-semibold text-foreground text-xl">
              Processing timeline
            </h2>
          </div>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-medium text-muted-foreground text-xs">
            Live updates enabled
          </span>
        </div>
      </div>

      <div className="px-5 py-5">
        <div className="space-y-5">
          {steps.map((step, index) => {
            const isLast = index === steps.length - 1;
            const stateMeta = getStateMeta(step.state);

            return (
              <div className="relative flex gap-4" key={step.id}>
                {!isLast && (
                  <div
                    className={`absolute top-11 bottom-0 left-5 w-px ${stateMeta.connectorClassName}`}
                  />
                )}

                <div
                  className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${stateMeta.iconClassName}`}
                >
                  <StatusIcon state={step.state} />
                </div>

                <div className="min-w-0 flex-1 pb-5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p
                        className={`font-semibold text-[11px] uppercase tracking-[0.18em] ${stateMeta.labelClassName}`}
                      >
                        {step.label}
                      </p>
                      <p className="mt-2 text-foreground text-sm leading-6">
                        {step.detail}
                      </p>
                    </div>
                    {step.meta && (
                      <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 font-medium text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
                        {step.meta}
                      </span>
                    )}
                  </div>

                  {step.error && (
                    <div className="mt-3 rounded-2xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-red-100 text-sm leading-6">
                      {step.error}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
