import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  createTranscriptComment,
  createTranslationJob,
  deleteTranscriptComment,
  downloadTranscriptExport,
  fetchTranscriptComments,
  downloadTranslatedTranscriptExport,
  fetchTranscriptRevisions,
  fetchTranslatedTranscripts,
  fetchTranslationJobs,
  restoreTranscriptRevision,
  updateTranscriptReview,
  updateTranscriptSegments,
  updateTranscriptSpeakerAliases,
  updateTranslatedTranscriptSegments,
} from "../api/videoService";
import type {
  Transcript,
  TranslationGlossaryTerm,
  TranscriptRevision,
  TranscriptSegment as TranscriptSegmentType,
  TranslatedTranscript,
  TranslationJob,
  TranslationJobMetrics,
  TranslationQaMetrics,
} from "../types/domain";
import {
  normalizeTranslatedTranscript,
  sortByNewest,
} from "../utils/transcript";
import TranscriptSegment from "./TranscriptSegment";

const AVAILABLE_LANGUAGES = [
  { code: "en", name: "English", flag: "🇺🇸" },
  { code: "es", name: "Spanish", flag: "🇪🇸" },
  { code: "fr", name: "French", flag: "🇫🇷" },
  { code: "de", name: "German", flag: "🇩🇪" },
  { code: "it", name: "Italian", flag: "🇮🇹" },
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
  { code: "ko", name: "Korean", flag: "🇰🇷" },
  { code: "nl", name: "Dutch", flag: "🇳🇱" },
  { code: "pt", name: "Portuguese", flag: "🇵🇹" },
  { code: "zh", name: "Chinese", flag: "🇨🇳" },
] as const;

type ExportFormat = "ass" | "json" | "review_package" | "txt" | "srt" | "vtt";

function GlobeIcon() {
  return (
    <svg
      className="inline-block h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>Language Globe</title>
      <path
        d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CheckMarkIcon() {
  return (
    <svg
      className="h-5 w-5 text-emerald-300"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>Checkmark</title>
      <path
        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LoadingIcon() {
  return (
    <svg
      className="h-5 w-5 animate-spin text-primary"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>Loading Spinner</title>
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        fill="currentColor"
      />
    </svg>
  );
}

function isActiveJob(job: TranslationJob): boolean {
  return job.status === "pending" || job.status === "processing";
}

function getTranslationMetrics(
  job: TranslationJob | null | undefined
): TranslationJobMetrics | null {
  const metrics = job?.error_details?.metrics;
  if (!metrics || typeof metrics !== "object" || Array.isArray(metrics)) {
    return null;
  }

  return metrics;
}

function formatDuration(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || Number.isNaN(seconds)) {
    return null;
  }

  if (seconds < 1) {
    return `${Math.round(seconds * 1000)} ms`;
  }

  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

function getLanguageName(languageCode: string | null | undefined): string {
  if (!languageCode) {
    return "Selected language";
  }

  return (
    AVAILABLE_LANGUAGES.find((language) => language.code === languageCode)
      ?.name ?? languageCode.toUpperCase()
  );
}

function getTranslationStrategyLabel(
  strategy: string | undefined
): string | null {
  switch (strategy) {
    case "cache_hit":
      return "Reused cached translation";
    case "segment_batches":
      return "Batch-translated transcript segments";
    case "full_content":
      return "Translated full transcript text";
    case "copy":
      return "Reused original text because the languages already matched";
    default:
      return null;
  }
}

function getLanguageConfig(languageCode: string | null | undefined) {
  return AVAILABLE_LANGUAGES.find((language) => language.code === languageCode);
}

function getLanguageFlag(languageCode: string | null | undefined): string {
  return getLanguageConfig(languageCode)?.flag ?? "🌐";
}

function getExportFormatLabel(format: ExportFormat | null): string {
  switch (format) {
    case "ass":
      return "ASS";
    case "json":
      return "JSON";
    case "review_package":
      return "review package";
    case "srt":
      return "SRT";
    case "txt":
      return "TXT";
    case "vtt":
      return "VTT";
    default:
      return "export";
  }
}

function parseGlossaryDraft(draft: string): TranslationGlossaryTerm[] {
  return draft
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(.+?)\s*(?:=>|->|:)\s*(.+)$/);
      const sourceTerm = match?.[1]?.trim();
      const targetTerm = match?.[2]?.trim();
      if (!sourceTerm || !targetTerm) {
        return null;
      }

      return {
        source_term: sourceTerm,
        target_term: targetTerm,
      };
    })
    .filter(
      (term): term is TranslationGlossaryTerm =>
        Boolean(term?.source_term && term.target_term)
    );
}

function getTranslationQaMetrics(
  translation: TranslatedTranscript | null,
  metrics: TranslationJobMetrics | null
): TranslationQaMetrics | null {
  return translation?.qa_metrics ?? metrics?.qa_metrics ?? null;
}

function formatRevisionTimestamp(createdAt: string): string {
  const timestamp = new Date(createdAt);
  if (Number.isNaN(timestamp.getTime())) {
    return "Unknown time";
  }

  return timestamp.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function getReviewStatusLabel(reviewStatus: string): string {
  switch (reviewStatus) {
    case "in_review":
      return "In review";
    case "approved":
      return "Approved";
    case "needs_changes":
      return "Needs changes";
    default:
      return "Draft";
  }
}

function countUniqueSpeakers(
  segments: TranscriptSegmentType[] | null | undefined
): number {
  const speakerIds = new Set<string>();

  for (const segment of segments ?? []) {
    if (segment.speaker) {
      speakerIds.add(segment.speaker);
    }
  }

  return speakerIds.size;
}

function createDefaultSpeakerNames(
  segments: TranscriptSegmentType[] | null | undefined
): Record<string, string> {
  const speakerIds: string[] = [];

  for (const segment of segments ?? []) {
    if (segment.speaker && !speakerIds.includes(segment.speaker)) {
      speakerIds.push(segment.speaker);
    }
  }

  const speakerNames: Record<string, string> = {};

  speakerIds.forEach((speakerId, index) => {
    speakerNames[speakerId] = `Speaker ${index + 1}`;
  });

  return speakerNames;
}

function getSegmentKey(segment: TranscriptSegmentType): string {
  return String(
    segment.id || `${segment.start_time}-${segment.text.slice(0, 10)}`
  );
}

interface TranscriptListProps {
  currentTime: number;
  onDisplayedTranscriptChange?: (
    transcript: Transcript | TranslatedTranscript
  ) => void;
  onSegmentClick: (time: number) => void;
  onTranscriptUpdated?: () => void;
  transcript: Transcript | null;
}

export default function TranscriptList({
  transcript,
  currentTime,
  onDisplayedTranscriptChange,
  onSegmentClick,
  onTranscriptUpdated,
}: TranscriptListProps) {
  const queryClient = useQueryClient();
  const segmentRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const translateMenuRef = useRef<HTMLDivElement | null>(null);
  const exportMenuRef = useRef<HTMLDivElement | null>(null);
  const historyMenuRef = useRef<HTMLDivElement | null>(null);
  const transcriptId = transcript?.id ?? "";
  const videoId = transcript?.video_id ?? "";
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeaker, setShowSpeaker] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [historyMenuOpen, setHistoryMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [commentDraft, setCommentDraft] = useState("");
  const [reviewAssigneeDraft, setReviewAssigneeDraft] = useState("");
  const [reviewStatusDraft, setReviewStatusDraft] = useState<
    "approved" | "draft" | "in_review" | "needs_changes"
  >("draft");
  const [translateMenuOpen, setTranslateMenuOpen] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
  const [showTranslationModal, setShowTranslationModal] = useState(false);
  const [pendingLanguage, setPendingLanguage] = useState<string | null>(null);
  const [translationStyleGuideDraft, setTranslationStyleGuideDraft] =
    useState("");
  const [translationGlossaryDraft, setTranslationGlossaryDraft] = useState("");
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({});
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(
    null
  );

  const translationJobsQuery = useQuery({
    queryKey: ["translationJobs", transcriptId],
    queryFn: async () =>
      transcriptId ? fetchTranslationJobs(transcriptId) : [],
    enabled: Boolean(transcriptId),
    select: (jobs) => sortByNewest(jobs),
  });
  const translationsQuery = useQuery({
    queryKey: ["translations", transcriptId],
    queryFn: async () => {
      const translations = transcriptId
        ? await fetchTranslatedTranscripts(transcriptId)
        : [];
      return translations
        .map((item) => normalizeTranslatedTranscript(item))
        .filter((item): item is TranslatedTranscript => item !== null);
    },
    enabled: Boolean(transcriptId),
    select: (translations) =>
      Object.fromEntries(
        translations.map((item) => [item.language, item])
      ) as Record<string, TranslatedTranscript>,
  });
  const transcriptRevisionsQuery = useQuery({
    queryKey: ["transcriptRevisions", transcriptId],
    queryFn: async () =>
      transcriptId ? fetchTranscriptRevisions(transcriptId) : [],
    enabled: Boolean(transcriptId),
  });
  const transcriptCommentsQuery = useQuery({
    queryKey: ["transcriptComments", transcriptId],
    queryFn: async () =>
      transcriptId ? fetchTranscriptComments(transcriptId) : [],
    enabled: Boolean(transcriptId),
  });
  const createTranslationMutation = useMutation({
    mutationFn: (payload: {
      glossaryTerms: TranslationGlossaryTerm[];
      language: string;
      styleGuide: string | null;
    }) =>
      createTranslationJob(transcriptId, payload.language, {
        glossaryTerms: payload.glossaryTerms,
        styleGuide: payload.styleGuide,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["translationJobs", transcriptId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["translations", transcriptId],
      });
    },
  });
  const updateOriginalTranscriptMutation = useMutation({
    mutationFn: (payload: {
      transcriptId: string;
      segments: TranscriptSegmentType[];
      content: string;
    }) =>
      updateTranscriptSegments(payload.transcriptId, {
        segments: payload.segments,
        content: payload.content,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["transcripts", videoId],
      });
      onTranscriptUpdated?.();
    },
  });
  const updateTranslatedTranscriptMutation = useMutation({
    mutationFn: (payload: {
      translatedTranscriptId: string;
      segments: TranscriptSegmentType[];
      content: string;
    }) =>
      updateTranslatedTranscriptSegments(payload.translatedTranscriptId, {
        segments: payload.segments,
        content: payload.content,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["translations", transcriptId],
      });
      onTranscriptUpdated?.();
    },
  });
  const updateSpeakerAliasesMutation = useMutation({
    mutationFn: (payload: {
      transcriptId: string;
      speakerAliases: Record<string, string>;
    }) =>
      updateTranscriptSpeakerAliases(
        payload.transcriptId,
        payload.speakerAliases
      ),
    onSuccess: async (updatedTranscript) => {
      const defaultSpeakerNames = createDefaultSpeakerNames(
        updatedTranscript.segments
      );
      setSpeakerNames({
        ...defaultSpeakerNames,
        ...(updatedTranscript.speaker_aliases ?? {}),
      });
      await queryClient.invalidateQueries({
        queryKey: ["transcripts", videoId],
      });
      onTranscriptUpdated?.();
    },
  });
  const restoreTranscriptRevisionMutation = useMutation({
    mutationFn: (payload: { transcriptId: string; revisionId: string }) =>
      restoreTranscriptRevision(payload.transcriptId, payload.revisionId),
    onSuccess: async (updatedTranscript) => {
      const defaultSpeakerNames = createDefaultSpeakerNames(
        updatedTranscript.segments
      );
      setSpeakerNames({
        ...defaultSpeakerNames,
        ...(updatedTranscript.speaker_aliases ?? {}),
      });
      setSelectedLanguage(null);
      setHistoryMenuOpen(false);
      await queryClient.invalidateQueries({
        queryKey: ["transcripts", videoId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["transcriptRevisions", transcriptId],
      });
      onTranscriptUpdated?.();
    },
  });
  const updateTranscriptReviewMutation = useMutation({
    mutationFn: (payload: {
      review_assignee?: string | null;
      review_status: "approved" | "draft" | "in_review" | "needs_changes";
    }) => updateTranscriptReview(transcriptId, payload),
    onSuccess: async (updatedTranscript) => {
      setReviewStatusDraft(
        (updatedTranscript.review_status as
          | "approved"
          | "draft"
          | "in_review"
          | "needs_changes") ?? "draft"
      );
      setReviewAssigneeDraft(updatedTranscript.review_assignee ?? "");
      await queryClient.invalidateQueries({
        queryKey: ["transcripts", videoId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["transcriptRevisions", transcriptId],
      });
      onTranscriptUpdated?.();
    },
  });
  const createTranscriptCommentMutation = useMutation({
    mutationFn: (payload: {
      author_name?: string;
      body: string;
      segment_id?: number;
      timestamp_seconds?: number;
    }) => createTranscriptComment(transcriptId, payload),
    onSuccess: async () => {
      setCommentDraft("");
      await queryClient.invalidateQueries({
        queryKey: ["transcriptComments", transcriptId],
      });
    },
  });
  const deleteTranscriptCommentMutation = useMutation({
    mutationFn: (commentId: string) => deleteTranscriptComment(commentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["transcriptComments", transcriptId],
      });
    },
  });

  const translations = translationsQuery.data ?? {};
  const transcriptComments = transcriptCommentsQuery.data ?? [];
  const transcriptRevisions = transcriptRevisionsQuery.data ?? [];
  const translationJobs = translationJobsQuery.data ?? [];
  const activeTranslationJobs = translationJobs.filter(isActiveJob);
  const selectedTranslationJob = selectedLanguage
    ? (translationJobs.find(
        (job) => job.target_language === selectedLanguage
      ) ?? null)
    : null;
  const selectedTranslationMetrics = getTranslationMetrics(
    selectedTranslationJob
  );
  const selectedTranslation =
    selectedLanguage && translations[selectedLanguage]
      ? translations[selectedLanguage]
      : null;
  const selectedTranslationQaMetrics = getTranslationQaMetrics(
    selectedTranslation,
    selectedTranslationMetrics
  );
  const currentTranscriptData = selectedLanguage
    ? (selectedTranslation ?? null)
    : transcript;
  const currentTranscriptContent = currentTranscriptData?.content ?? "";
  const currentSegments = currentTranscriptData?.segments ?? [];
  const filteredSegments = searchQuery
    ? currentSegments.filter((segment) =>
        segment.text.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : currentSegments;
  const isLoadingSelectedTranslation =
    !!selectedLanguage &&
    !translations[selectedLanguage] &&
    activeTranslationJobs.some(
      (job) => job.target_language === selectedLanguage
    );
  const translatedLanguageCodes = AVAILABLE_LANGUAGES.filter(
    (language) => !!translations[language.code]
  ).map((language) => language.code);
  const pendingLanguageCodes = AVAILABLE_LANGUAGES.filter(
    (language) =>
      activeTranslationJobs.some(
        (job) => job.target_language === language.code
      ) && !translations[language.code]
  ).map((language) => language.code);

  useEffect(() => {
    if (!transcriptId) {
      setSpeakerNames({});
      return;
    }

    const defaultSpeakerNames = createDefaultSpeakerNames(transcript?.segments);
    const mergedSpeakerNames = {
      ...defaultSpeakerNames,
      ...(transcript?.speaker_aliases ?? {}),
    };

    setSpeakerNames(mergedSpeakerNames);
  }, [transcript?.segments, transcript?.speaker_aliases, transcriptId]);

  useEffect(() => {
    setReviewStatusDraft(
      (transcript?.review_status as
        | "approved"
        | "draft"
        | "in_review"
        | "needs_changes") ?? "draft"
    );
    setReviewAssigneeDraft(transcript?.review_assignee ?? "");
  }, [transcript?.review_assignee, transcript?.review_status]);

  useEffect(() => {
    if (currentTranscriptData) {
      onDisplayedTranscriptChange?.(currentTranscriptData);
    }
  }, [currentTranscriptData, onDisplayedTranscriptChange]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent): void {
      if (!(event.target instanceof Node)) {
        return;
      }

      if (
        translateMenuOpen &&
        translateMenuRef.current &&
        !translateMenuRef.current.contains(event.target)
      ) {
        setTranslateMenuOpen(false);
      }

      if (
        menuOpen &&
        exportMenuRef.current &&
        !exportMenuRef.current.contains(event.target)
      ) {
        setMenuOpen(false);
      }

      if (
        historyMenuOpen &&
        historyMenuRef.current &&
        !historyMenuRef.current.contains(event.target)
      ) {
        setHistoryMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key !== "Escape") {
        return;
      }

      setTranslateMenuOpen(false);
      setMenuOpen(false);
      setHistoryMenuOpen(false);

      if (showTranslationModal) {
        setShowTranslationModal(false);
        setPendingLanguage(null);
        setTranslationStyleGuideDraft("");
        setTranslationGlossaryDraft("");
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [historyMenuOpen, menuOpen, showTranslationModal, translateMenuOpen]);

  if (!transcript) {
    return (
      <div className="panel flex h-full min-h-[24rem] items-center justify-center p-6">
        <div className="max-w-sm text-center">
          <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
            Transcript
          </p>
          <h3 className="mt-2 font-semibold text-foreground text-xl">
            Waiting for transcript data
          </h3>
          <p className="mt-3 text-muted-foreground leading-6">
            The transcript editor will unlock here as soon as the transcription
            step finishes.
          </p>
        </div>
      </div>
    );
  }

  function findActiveSegment(): TranscriptSegmentType | null {
    if (currentTime < 0) {
      return null;
    }

    for (let index = 0; index < currentSegments.length; index += 1) {
      const segment = currentSegments[index];
      if (!segment) {
        continue;
      }

      const nextSegment = currentSegments[index + 1];
      const nextStart = nextSegment
        ? nextSegment.start_time
        : Number.POSITIVE_INFINITY;

      if (currentTime >= segment.start_time && currentTime < nextStart) {
        return segment;
      }
    }

    return null;
  }

  async function handleConfirmTranslation(): Promise<void> {
    if (!pendingLanguage) {
      return;
    }

    await createTranslationMutation.mutateAsync({
      language: pendingLanguage,
      styleGuide: translationStyleGuideDraft.trim() || null,
      glossaryTerms: parseGlossaryDraft(translationGlossaryDraft),
    });
    setSelectedLanguage(pendingLanguage);
    setPendingLanguage(null);
    setShowTranslationModal(false);
    setTranslationStyleGuideDraft("");
    setTranslationGlossaryDraft("");
  }

  async function handleEditSegment(
    segmentId: number,
    newText: string
  ): Promise<void> {
    const updatedSegments = currentSegments.map((segment) =>
      segment.id === segmentId ? { ...segment, text: newText } : segment
    );
    const updatedContent = updatedSegments
      .map((segment) => segment.text)
      .join(" ");

    if (selectedLanguage && translations[selectedLanguage]) {
      await updateTranslatedTranscriptMutation.mutateAsync({
        translatedTranscriptId: translations[selectedLanguage].id,
        segments: updatedSegments,
        content: updatedContent,
      });
      return;
    }

    await updateOriginalTranscriptMutation.mutateAsync({
      transcriptId,
      segments: updatedSegments,
      content: updatedContent,
    });
  }

  function handleConfirmTranslationClick(): void {
    handleConfirmTranslation().catch((error) => {
      console.error("Failed to request translation:", error);
    });
  }

  function handleRenameSpeaker(speakerId: string, newName: string): void {
    if (!transcriptId) {
      return;
    }

    const trimmedName = newName.trim();
    const defaultSpeakerNames = createDefaultSpeakerNames(transcript?.segments);
    const previousSpeakerNames = speakerNames;
    const nextSpeakerNames = {
      ...defaultSpeakerNames,
      ...speakerNames,
      [speakerId]: trimmedName || defaultSpeakerNames[speakerId] || speakerId,
    };

    setSpeakerNames(nextSpeakerNames);
    updateSpeakerAliasesMutation.mutate(
      {
        transcriptId,
        speakerAliases: nextSpeakerNames,
      },
      {
        onError: (error) => {
          console.error("Failed to persist speaker aliases:", error);
          setSpeakerNames(previousSpeakerNames);
        },
      }
    );
  }

  function formatRevisionReason(revision: TranscriptRevision): string {
    if (revision.reason.startsWith("restore_revision_")) {
      const restoredRevisionNumber = revision.reason.replace(
        "restore_revision_",
        ""
      );
      return `Restored from revision ${restoredRevisionNumber}`;
    }

    switch (revision.reason) {
      case "initial_import":
        return "Initial import";
      case "segment_edit":
        return "Segment edit";
      case "speaker_alias_update":
        return "Speaker rename";
      default:
        return revision.reason.replace(/_/g, " ");
    }
  }

  function handleRestoreRevision(revisionId: string): void {
    restoreTranscriptRevisionMutation.mutate({
      transcriptId,
      revisionId,
    });
  }

  function handleSaveReviewState(): void {
    updateTranscriptReviewMutation.mutate({
      review_status: reviewStatusDraft,
      review_assignee: reviewAssigneeDraft.trim() || null,
    });
  }

  function handleCreateComment(): void {
    const trimmedBody = commentDraft.trim();
    if (!trimmedBody || !transcriptId) {
      return;
    }

    createTranscriptCommentMutation.mutate({
      author_name: reviewAssigneeDraft.trim() || "Local Reviewer",
      body: trimmedBody,
      segment_id: activeSegment?.id,
      timestamp_seconds: activeSegment?.start_time ?? currentTime,
    });
  }

  async function handleDownloadTranscript(format: ExportFormat): Promise<void> {
    if (!transcriptId) {
      return;
    }

    setExportError(null);
    setExportingFormat(format);

    try {
      if (
        format !== "review_package" &&
        selectedLanguage &&
        translations[selectedLanguage]
      ) {
        await downloadTranslatedTranscriptExport(translations[selectedLanguage].id, {
          format,
          includeSpeakers: showSpeaker,
          includeTimestamps: showTimestamps,
        });
        return;
      }

      await downloadTranscriptExport(transcriptId, {
        format,
        includeSpeakers: showSpeaker,
        includeTimestamps: showTimestamps,
      });
    } catch (error) {
      console.error("Failed to download transcript export:", error);
      setExportError("Export failed. Please try again.");
    } finally {
      setExportingFormat(null);
    }
  }

  function formatTimeForDownload(seconds: number | undefined | null): string {
    if (seconds === undefined || seconds === null) {
      return "00:00:00";
    }

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`;
  }

  const activeSegment = findActiveSegment();
  const selectedTranslationDuration =
    formatDuration(selectedTranslationJob?.processing_time_seconds) ??
    formatDuration(selectedTranslationMetrics?.total_processing_seconds);
  const selectedTranslationModelDuration = formatDuration(
    selectedTranslationMetrics?.translation_seconds
  );
  const selectedTranslationPersistDuration = formatDuration(
    selectedTranslationMetrics?.persist_seconds
  );
  const selectedTranslationDetectionDuration = formatDuration(
    selectedTranslationMetrics?.language_detection_seconds
  );
  const selectedTranslationStrategyLabel = getTranslationStrategyLabel(
    selectedTranslationMetrics?.translation_strategy
  );
  const selectedTranslationGlossaryCount =
    selectedTranslation?.glossary_terms?.length ??
    selectedTranslationMetrics?.glossary_term_count ??
    0;
  const selectedTranslationHasStyleGuide =
    Boolean(selectedTranslation?.style_guide) ||
    Boolean(selectedTranslationMetrics?.style_guide_used);
  const activePlayheadLabel =
    activeSegment && currentTime >= 0
      ? formatTimeForDownload(activeSegment.start_time)
      : "No active cue";
  const visibleSegmentCount = filteredSegments.length;
  const speakerCount = countUniqueSpeakers(currentSegments);
  const transcriptHeading = selectedLanguage
    ? `Transcript (${getLanguageName(selectedLanguage)})`
    : "Transcript";
  const transcriptDescription = selectedLanguage
    ? `Viewing the ${getLanguageName(selectedLanguage)} translation.`
    : `Viewing the original ${getLanguageName(transcript.language_code)} transcript.`;
  const showNoSearchMatches =
    !isLoadingSelectedTranslation &&
    currentSegments.length > 0 &&
    searchQuery.trim().length > 0 &&
      filteredSegments.length === 0;
  const currentReviewLabel = getReviewStatusLabel(reviewStatusDraft);
  const commentTargetLabel = activeSegment
    ? `Commenting on ${formatTimeForDownload(activeSegment.start_time)}`
    : `Commenting at ${formatTimeForDownload(currentTime)}`;

  function scrollToCurrentSegment(): void {
    if (!activeSegment) {
      return;
    }

    const segmentElement = segmentRefs.current[getSegmentKey(activeSegment)];
    segmentElement?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  return (
    <div className="panel flex h-full flex-col overflow-hidden p-4 sm:p-5">
      <div className="mb-4 flex flex-col gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
              Transcript
            </p>
            <h3 className="mt-2 font-semibold text-foreground text-xl">
              {transcriptHeading}
            </h3>
            <p className="mt-2 text-muted-foreground text-sm">
              {transcriptDescription} Search, edit, export, and move through the
              spoken timeline.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 font-medium text-emerald-200 text-sm transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!activeSegment || isLoadingSelectedTranslation}
              onClick={scrollToCurrentSegment}
              type="button"
            >
              Scroll to current
            </button>
            <div
              className="relative inline-block text-left"
              ref={translateMenuRef}
            >
              <button
                className="flex items-center rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground"
                onClick={() => setTranslateMenuOpen(!translateMenuOpen)}
                type="button"
              >
                <GlobeIcon />
                <span className="ml-2">Translate</span>
              </button>
              {translateMenuOpen && (
                <div className="panel absolute right-0 z-20 mt-2 w-64 origin-top-right rounded-[1.25rem] border-white/10 bg-card/95 p-2 focus:outline-none">
                  <div
                    aria-labelledby="translate-options-menu"
                    aria-orientation="vertical"
                    className="space-y-1"
                    role="menu"
                  >
                    <div className="px-3 py-2 font-semibold text-foreground text-sm">
                      Select language
                    </div>
                    {transcript.language_code && (
                      <button
                        className={`block w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                          selectedLanguage
                            ? "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                            : "bg-white/8 text-foreground"
                        }`}
                        onClick={() => {
                          setSelectedLanguage(null);
                          setTranslateMenuOpen(false);
                        }}
                        role="menuitem"
                        type="button"
                      >
                        Show original ({transcript.language_code.toUpperCase()})
                      </button>
                    )}
                    {AVAILABLE_LANGUAGES.map((language) => {
                      const isOriginalLanguage =
                        language.code === transcript.language_code;
                      const isSelected = selectedLanguage === language.code;
                      const translationExists = !!translations[language.code];
                      const hasActiveJob = activeTranslationJobs.some(
                        (job) => job.target_language === language.code
                      );

                      return (
                        <button
                          className={`block flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                            (isSelected && !isOriginalLanguage) ||
                            (!selectedLanguage && isOriginalLanguage)
                              ? "bg-white/8 text-foreground"
                              : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                          }`}
                          disabled={isSelected && !isOriginalLanguage}
                          key={language.code}
                          onClick={() => {
                            if (isOriginalLanguage) {
                              setSelectedLanguage(null);
                              setTranslateMenuOpen(false);
                              return;
                            }

                            if (translationExists) {
                              setSelectedLanguage(language.code);
                              setTranslateMenuOpen(false);
                              return;
                            }

                            setPendingLanguage(language.code);
                            setShowTranslationModal(true);
                            setTranslateMenuOpen(false);
                          }}
                          role="menuitem"
                          type="button"
                        >
                          <span>
                            {language.flag} {language.name}
                          </span>
                          {translationExists &&
                            language.code !== transcript.language_code && (
                              <CheckMarkIcon />
                            )}
                          {hasActiveJob && <LoadingIcon />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div
              className="relative inline-block text-left"
              ref={exportMenuRef}
            >
              <div
                className="relative inline-block text-left"
                ref={historyMenuRef}
              >
                <button
                  className="mr-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                  onClick={() => setHistoryMenuOpen(!historyMenuOpen)}
                  type="button"
                >
                  History
                </button>
                {historyMenuOpen && (
                  <div className="panel absolute right-full z-10 mt-2 mr-2 max-h-80 w-80 overflow-y-auto rounded-[1.25rem] border-white/10 bg-card/95 p-2 focus:outline-none">
                    <div className="space-y-1" role="menu">
                      <div className="px-3 py-2 font-semibold text-foreground text-sm">
                        Revision history
                      </div>
                      {transcriptRevisions.length === 0 ? (
                        <div className="px-3 py-2 text-muted-foreground text-sm">
                          No saved revisions yet.
                        </div>
                      ) : (
                        transcriptRevisions.map((revision, index) => (
                          <div
                            className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2"
                            key={revision.id}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium text-foreground text-sm">
                                  Revision {revision.revision_number}
                                </p>
                                <p className="mt-1 text-muted-foreground text-xs">
                                  {formatRevisionReason(revision)}
                                </p>
                                <p className="mt-1 text-muted-foreground/80 text-[11px]">
                                  {formatRevisionTimestamp(revision.created_at)}
                                </p>
                              </div>
                              {index === 0 ? (
                                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 font-medium text-[11px] text-emerald-200">
                                  Current
                                </span>
                              ) : (
                                <button
                                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                                  disabled={
                                    restoreTranscriptRevisionMutation.isPending
                                  }
                                  onClick={() =>
                                    handleRestoreRevision(revision.id)
                                  }
                                  type="button"
                                >
                                  Restore revision {revision.revision_number}
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                onClick={() => setMenuOpen(!menuOpen)}
                type="button"
              >
                {exportingFormat
                  ? `Preparing ${getExportFormatLabel(exportingFormat)}...`
                  : "Export"}
              </button>
              {menuOpen && (
                <div className="panel absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-[1.25rem] border-white/10 bg-card/95 p-2 focus:outline-none">
                  <div
                    aria-labelledby="options-menu"
                    aria-orientation="vertical"
                    className="space-y-1"
                    role="menu"
                  >
                    <div className="px-3 py-2 font-semibold text-foreground text-sm">
                      Export transcript
                    </div>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        void handleDownloadTranscript("txt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                      disabled={Boolean(exportingFormat)}
                    >
                      Download as TXT
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        void handleDownloadTranscript("srt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                      disabled={Boolean(exportingFormat)}
                    >
                      Download as SRT
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        void handleDownloadTranscript("vtt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                      disabled={Boolean(exportingFormat)}
                    >
                      Download as VTT
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        void handleDownloadTranscript("json");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                      disabled={Boolean(exportingFormat)}
                    >
                      Download as JSON
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        void handleDownloadTranscript("ass");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                      disabled={Boolean(exportingFormat)}
                    >
                      Download as ASS
                    </button>
                    {!selectedLanguage && (
                      <button
                        className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                        onClick={() => {
                          void handleDownloadTranscript("review_package");
                          setMenuOpen(false);
                        }}
                        role="menuitem"
                        type="button"
                        disabled={Boolean(exportingFormat)}
                      >
                        Download review package
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            className={`rounded-full border px-3 py-2 font-medium text-sm transition ${
              selectedLanguage === null
                ? "border-primary/25 bg-primary/10 text-primary"
                : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
            }`}
            onClick={() => setSelectedLanguage(null)}
            type="button"
          >
            {getLanguageFlag(transcript.language_code)} Original
          </button>

          {translatedLanguageCodes.map((languageCode) => (
            <button
              className={`rounded-full border px-3 py-2 font-medium text-sm transition ${
                selectedLanguage === languageCode
                  ? "border-primary/25 bg-primary/10 text-primary"
                  : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
              }`}
              key={languageCode}
              onClick={() => setSelectedLanguage(languageCode)}
              type="button"
            >
              {getLanguageFlag(languageCode)} {getLanguageName(languageCode)}
            </button>
          ))}

          {pendingLanguageCodes.map((languageCode) => (
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 font-medium text-sm ${
                selectedLanguage === languageCode
                  ? "border-primary/25 bg-primary/10 text-primary"
                  : "border-sky-400/20 bg-sky-400/10 text-sky-100"
              }`}
              key={languageCode}
            >
              <LoadingIcon />
              {getLanguageFlag(languageCode)} {getLanguageName(languageCode)}
            </span>
          ))}

          {translatedLanguageCodes.length === 0 &&
            pendingLanguageCodes.length === 0 && (
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-muted-foreground text-sm">
                No translated versions yet
              </span>
            )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-muted-foreground">
            {exportingFormat
              ? `Preparing ${getExportFormatLabel(exportingFormat)} download from the backend`
              : "Backend-generated exports stay aligned with the saved review state"}
          </span>
          {exportError ? (
            <span className="rounded-full border border-destructive/20 bg-destructive/10 px-3 py-2 text-destructive">
              {exportError}
            </span>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Visible segments
            </p>
            <p className="mt-2 text-foreground text-sm">
              {visibleSegmentCount}
              <span className="ml-2 text-muted-foreground">
                / {currentSegments.length}
              </span>
            </p>
          </div>

          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Speakers
            </p>
            <p className="mt-2 text-foreground text-sm">
              {speakerCount > 0 ? speakerCount : "None"}
            </p>
          </div>

          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Playhead
            </p>
            <p className="mt-2 text-foreground text-sm">
              {activePlayheadLabel}
            </p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <section className="rounded-2xl border border-white/8 bg-white/5 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
                  Review status
                </p>
                <p className="mt-2 text-foreground text-sm">
                  {currentReviewLabel}
                </p>
              </div>
              <select
                className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-foreground text-sm"
                onChange={(event) =>
                  setReviewStatusDraft(
                    event.target.value as
                      | "approved"
                      | "draft"
                      | "in_review"
                      | "needs_changes"
                  )
                }
                value={reviewStatusDraft}
              >
                <option value="draft">Draft</option>
                <option value="in_review">In review</option>
                <option value="approved">Approved</option>
                <option value="needs_changes">Needs changes</option>
              </select>
            </div>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <input
                className="flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm placeholder:text-muted-foreground/80"
                onChange={(event) => setReviewAssigneeDraft(event.target.value)}
                placeholder="Assignee or reviewer"
                type="text"
                value={reviewAssigneeDraft}
              />
              <button
                className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                disabled={updateTranscriptReviewMutation.isPending}
                onClick={handleSaveReviewState}
                type="button"
              >
                Save review
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/8 bg-white/5 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
                  Review comments
                </p>
                <p className="mt-2 text-muted-foreground text-sm">
                  {commentTargetLabel}
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-muted-foreground text-xs">
                {transcriptComments.length} comment
                {transcriptComments.length === 1 ? "" : "s"}
              </span>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              <textarea
                className="min-h-[96px] rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-foreground text-sm placeholder:text-muted-foreground/80"
                onChange={(event) => setCommentDraft(event.target.value)}
                placeholder="Add a timestamp-linked review note"
                value={commentDraft}
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-muted-foreground text-xs">
                  New comments attach to the active segment when available.
                </p>
                <button
                  className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={
                    createTranscriptCommentMutation.isPending ||
                    commentDraft.trim().length === 0
                  }
                  onClick={handleCreateComment}
                  type="button"
                >
                  Add comment
                </button>
              </div>
            </div>

            <div className="mt-4 max-h-52 space-y-3 overflow-y-auto">
              {transcriptComments.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No review comments yet.
                </p>
              ) : (
                transcriptComments.map((comment) => (
                  <div
                    className="rounded-2xl border border-white/8 bg-background/40 px-4 py-3"
                    key={comment.id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        className="text-left"
                        onClick={() =>
                          onSegmentClick(comment.timestamp_seconds ?? 0)
                        }
                        type="button"
                      >
                        <p className="font-medium text-foreground text-sm">
                          {comment.author_name || "Local Reviewer"}
                        </p>
                        <p className="mt-1 text-muted-foreground text-xs">
                          {formatRevisionTimestamp(comment.created_at)}
                          {comment.timestamp_seconds !== null &&
                          comment.timestamp_seconds !== undefined
                            ? ` · ${formatTimeForDownload(comment.timestamp_seconds)}`
                            : ""}
                        </p>
                      </button>
                      <button
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={deleteTranscriptCommentMutation.isPending}
                        onClick={() =>
                          deleteTranscriptCommentMutation.mutate(comment.id)
                        }
                        type="button"
                      >
                        Delete
                      </button>
                    </div>
                    <p className="mt-3 text-sm text-slate-200">
                      {comment.body}
                    </p>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        <div className="relative">
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="m21 21-4.35-4.35M18 10.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <input
            className="w-full rounded-full border border-white/10 bg-white/5 py-3 pr-4 pl-11 text-foreground text-sm transition placeholder:text-muted-foreground/80 focus:border-primary/40 focus:bg-white/8 focus:outline-none focus:ring-2 focus:ring-primary/30"
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search transcript..."
            type="text"
            value={searchQuery}
          />
          {searchQuery && (
            <button
              className="absolute top-1/2 right-3 -translate-y-1/2 rounded-full border border-white/10 bg-white/5 px-3 py-1 font-medium text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground"
              onClick={() => setSearchQuery("")}
              type="button"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            className={`rounded-full border px-3 py-1.5 font-medium text-xs uppercase tracking-[0.18em] transition ${
              showTimestamps
                ? "border-primary/25 bg-primary/10 text-primary"
                : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
            }`}
            onClick={() => setShowTimestamps(!showTimestamps)}
            type="button"
          >
            {showTimestamps ? "Timestamps on" : "Timestamps off"}
          </button>

          <button
            className={`rounded-full border px-3 py-1.5 font-medium text-xs uppercase tracking-[0.18em] transition ${
              showSpeaker
                ? "border-primary/25 bg-primary/10 text-primary"
                : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
            }`}
            onClick={() => setShowSpeaker(!showSpeaker)}
            type="button"
          >
            {showSpeaker ? "Speakers on" : "Speakers off"}
          </button>

          {searchQuery.trim() && (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-muted-foreground text-xs uppercase tracking-[0.18em]">
              {visibleSegmentCount} result{visibleSegmentCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>

      {selectedLanguage && selectedTranslationJob && (
        <div className="mb-4 rounded-[1.25rem] border border-sky-400/20 bg-sky-400/10 p-4 text-sky-100">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">
              {selectedTranslationJob.status === "completed"
                ? `${getLanguageName(selectedLanguage)} translation ready`
                : `Translating to ${getLanguageName(selectedLanguage)}`}
            </p>
            {selectedTranslationMetrics?.cache_hit && (
              <span className="rounded-full bg-emerald-400/15 px-2 py-0.5 font-medium text-emerald-200 text-xs">
                Cached
              </span>
            )}
            {selectedTranslationDuration && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-sky-50 text-xs">
                {selectedTranslationDuration}
              </span>
            )}
            {selectedTranslationHasStyleGuide && (
              <span className="rounded-full bg-violet-400/15 px-2 py-0.5 font-medium text-violet-100 text-xs">
                Style guide
              </span>
            )}
            {selectedTranslationGlossaryCount > 0 && (
              <span className="rounded-full bg-amber-300/15 px-2 py-0.5 font-medium text-amber-100 text-xs">
                {selectedTranslationGlossaryCount} glossary term
                {selectedTranslationGlossaryCount === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <p className="mt-2 text-sky-100/80 text-sm">
            {selectedTranslationJob.status === "pending" &&
              "Queued and waiting for the translation worker to pick it up."}
            {selectedTranslationJob.status === "processing" &&
              "The local translation model is working through this transcript now."}
            {selectedTranslationJob.status === "completed" &&
              (selectedTranslationStrategyLabel ??
                "Translation completed successfully.")}
            {selectedTranslationJob.status === "failed" &&
              "Translation failed. Try requesting it again after checking the worker logs."}
          </p>
          {selectedTranslationJob.status === "completed" &&
            selectedTranslationMetrics && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {typeof selectedTranslationMetrics.segment_count === "number" &&
                  selectedTranslationMetrics.segment_count > 0 && (
                    <span className="rounded-full bg-white/10 px-2 py-1">
                      {selectedTranslationMetrics.segment_count} segments
                    </span>
                  )}
                {selectedTranslationModelDuration && (
                  <span className="rounded-full bg-white/10 px-2 py-1">
                    Model time: {selectedTranslationModelDuration}
                  </span>
                )}
                {selectedTranslationPersistDuration && (
                  <span className="rounded-full bg-white/10 px-2 py-1">
                    Save time: {selectedTranslationPersistDuration}
                  </span>
                )}
                {selectedTranslationDetectionDuration &&
                  (selectedTranslationMetrics.language_detection_seconds ?? 0) >
                    0 && (
                    <span className="rounded-full bg-white/10 px-2 py-1">
                      Detect: {selectedTranslationDetectionDuration}
                    </span>
                  )}
              </div>
            )}
          {selectedTranslationJob.status === "completed" &&
            selectedTranslationQaMetrics && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-white/10 px-2 py-1">
                  QA: {selectedTranslationQaMetrics.segment_count ?? 0} segments
                </span>
                {(selectedTranslationQaMetrics.long_line_warnings ?? 0) > 0 && (
                  <span className="rounded-full bg-warning/20 px-2 py-1 text-warning">
                    {selectedTranslationQaMetrics.long_line_warnings} long lines
                  </span>
                )}
                {(selectedTranslationQaMetrics.high_cps_warnings ?? 0) > 0 && (
                  <span className="rounded-full bg-warning/20 px-2 py-1 text-warning">
                    {selectedTranslationQaMetrics.high_cps_warnings} fast cues
                  </span>
                )}
                {(selectedTranslationQaMetrics.overlap_warnings ?? 0) > 0 && (
                  <span className="rounded-full bg-warning/20 px-2 py-1 text-warning">
                    {selectedTranslationQaMetrics.overlap_warnings} overlaps
                  </span>
                )}
                {(selectedTranslationQaMetrics.missing_speaker_warnings ?? 0) >
                  0 && (
                  <span className="rounded-full bg-warning/20 px-2 py-1 text-warning">
                    {selectedTranslationQaMetrics.missing_speaker_warnings} missing
                    speaker labels
                  </span>
                )}
              </div>
            )}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {isLoadingSelectedTranslation && (
          <div className="space-y-3 py-1">
            {[0, 1, 2].map((index) => (
              <div
                className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4"
                key={index}
              >
                <div className="flex gap-2">
                  <div className="h-6 w-16 animate-pulse rounded-full bg-white/8" />
                  <div className="h-6 w-24 animate-pulse rounded-full bg-white/8" />
                </div>
                <div className="mt-3 h-5 w-full animate-pulse rounded bg-white/8" />
                <div className="mt-2 h-5 w-4/5 animate-pulse rounded bg-white/8" />
              </div>
            ))}
          </div>
        )}
        {showNoSearchMatches && (
          <div className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-6 text-center">
            <p className="font-semibold text-foreground text-lg">
              No matching transcript segments
            </p>
            <p className="mt-2 text-muted-foreground">
              Try a shorter phrase or clear the search to return to the full
              timeline.
            </p>
            <button
              className="mt-4 rounded-full border border-white/10 bg-white/5 px-4 py-2 font-medium text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
              onClick={() => setSearchQuery("")}
              type="button"
            >
              Clear search
            </button>
          </div>
        )}
        {!isLoadingSelectedTranslation &&
          currentSegments.length === 0 &&
          !showNoSearchMatches &&
          currentTranscriptContent && (
            <p className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-5 text-center text-muted-foreground">
              <span className="text-foreground">
                {currentTranscriptContent}
              </span>
            </p>
          )}
        {!isLoadingSelectedTranslation &&
          currentSegments.length === 0 &&
          !showNoSearchMatches &&
          !currentTranscriptContent && (
            <p className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-5 text-center text-muted-foreground">
              {selectedLanguage
                ? "No transcript segments are available for this language yet."
                : "No transcript segments available."}
            </p>
          )}
        {!isLoadingSelectedTranslation && filteredSegments.length > 0 && (
          <div className="space-y-3">
            {filteredSegments.map((segment) => (
              <div
                key={getSegmentKey(segment)}
                ref={(element) => {
                  segmentRefs.current[getSegmentKey(segment)] = element;
                }}
              >
                <TranscriptSegment
                  isActive={activeSegment?.start_time === segment.start_time}
                  isEditable
                  onClick={onSegmentClick}
                  onEdit={handleEditSegment}
                  onRenameSpeaker={handleRenameSpeaker}
                  segment={segment}
                  showSpeaker={showSpeaker && !selectedLanguage}
                  showTimestamps={showTimestamps}
                  speakerName={
                    segment.speaker
                      ? (speakerNames[segment.speaker] ?? segment.speaker)
                      : undefined
                  }
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {showTranslationModal && pendingLanguage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-md">
          <div className="panel-elevated mx-auto max-w-md border-white/10 bg-card/95 p-6">
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
              Translation
            </p>
            <h3 className="mt-2 font-semibold text-foreground text-lg">
              Translate Transcript
            </h3>
            <p className="mt-3 text-muted-foreground">
              The transcript will be translated to{" "}
              {AVAILABLE_LANGUAGES.find(
                (language) => language.code === pendingLanguage
              )?.name ?? pendingLanguage}
              . This may take a few moments.
            </p>
            <div className="mt-5 space-y-4">
              <label className="block">
                <span className="mb-2 block font-medium text-foreground text-sm">
                  Style guide
                </span>
                <textarea
                  className="min-h-24 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-foreground text-sm placeholder:text-muted-foreground/80 focus:border-primary/40 focus:bg-white/8 focus:outline-none focus:ring-2 focus:ring-primary/30"
                  onChange={(event) =>
                    setTranslationStyleGuideDraft(event.target.value)
                  }
                  placeholder="Optional instructions like tone, terminology preferences, or subtitle style."
                  value={translationStyleGuideDraft}
                />
              </label>
              <label className="block">
                <span className="mb-2 block font-medium text-foreground text-sm">
                  Glossary
                </span>
                <textarea
                  className="min-h-24 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-foreground text-sm placeholder:text-muted-foreground/80 focus:border-primary/40 focus:bg-white/8 focus:outline-none focus:ring-2 focus:ring-primary/30"
                  onChange={(event) =>
                    setTranslationGlossaryDraft(event.target.value)
                  }
                  placeholder={"One term per line, for example:\nAPI => Schnittstelle\nGPU => GPU"}
                  value={translationGlossaryDraft}
                />
                <p className="mt-2 text-muted-foreground text-xs">
                  Use one line per entry in the format <code>source =&gt; target</code>.
                </p>
              </label>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
                onClick={() => {
                  setShowTranslationModal(false);
                  setPendingLanguage(null);
                  setTranslationStyleGuideDraft("");
                  setTranslationGlossaryDraft("");
                }}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-full bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:bg-warning"
                onClick={handleConfirmTranslationClick}
                type="button"
              >
                Translate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
