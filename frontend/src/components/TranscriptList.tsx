import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  createTranslationJob,
  fetchTranslatedTranscripts,
  fetchTranslationJobs,
  updateTranscriptSegments,
  updateTranslatedTranscriptSegments,
} from "../api/videoService";
import type {
  Transcript,
  TranscriptSegment as TranscriptSegmentType,
  TranslatedTranscript,
  TranslationJob,
  TranslationJobMetrics,
} from "../types/domain";
import {
  downloadFile,
  generateSRT,
  generateTXT,
  generateVTT,
} from "../utils/exportUtils";
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
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
] as const;

const SPEAKER_NAME_STORAGE_PREFIX = "transcript-speaker-names";

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

function buildSpeakerStorageKey(transcriptId: string): string {
  return `${SPEAKER_NAME_STORAGE_PREFIX}:${transcriptId}`;
}

function getSpeakerNameStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  const storage = window.localStorage;

  if (
    !storage ||
    typeof storage.getItem !== "function" ||
    typeof storage.setItem !== "function"
  ) {
    return null;
  }

  return storage;
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

function readSpeakerNames(transcriptId: string): Record<string, string> {
  const storage = getSpeakerNameStorage();

  if (!storage) {
    return {};
  }

  try {
    const storedValue = storage.getItem(buildSpeakerStorageKey(transcriptId));
    if (!storedValue) {
      return {};
    }

    return JSON.parse(storedValue) as Record<string, string>;
  } catch (error) {
    console.error("Failed to read speaker names from local storage:", error);
    return {};
  }
}

function writeSpeakerNames(
  transcriptId: string,
  speakerNames: Record<string, string>
): void {
  const storage = getSpeakerNameStorage();

  if (!storage) {
    return;
  }

  try {
    storage.setItem(
      buildSpeakerStorageKey(transcriptId),
      JSON.stringify(speakerNames)
    );
  } catch (error) {
    console.error("Failed to write speaker names to local storage:", error);
  }
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
  const transcriptId = transcript?.id ?? "";
  const videoId = transcript?.video_id ?? "";
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeaker, setShowSpeaker] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [translateMenuOpen, setTranslateMenuOpen] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
  const [showTranslationModal, setShowTranslationModal] = useState(false);
  const [pendingLanguage, setPendingLanguage] = useState<string | null>(null);
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({});

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
  const createTranslationMutation = useMutation({
    mutationFn: (language: string) =>
      createTranslationJob(transcriptId, language),
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

  const translations = translationsQuery.data ?? {};
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
  const currentTranscriptData = selectedLanguage
    ? (translations[selectedLanguage] ?? null)
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
      ...readSpeakerNames(transcriptId),
    };

    setSpeakerNames(mergedSpeakerNames);
    writeSpeakerNames(transcriptId, mergedSpeakerNames);
  }, [transcript?.segments, transcriptId]);

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
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key !== "Escape") {
        return;
      }

      setTranslateMenuOpen(false);
      setMenuOpen(false);

      if (showTranslationModal) {
        setShowTranslationModal(false);
        setPendingLanguage(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen, showTranslationModal, translateMenuOpen]);

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

    await createTranslationMutation.mutateAsync(pendingLanguage);
    setSelectedLanguage(pendingLanguage);
    setPendingLanguage(null);
    setShowTranslationModal(false);
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
    const nextSpeakerNames = {
      ...speakerNames,
      [speakerId]: trimmedName || defaultSpeakerNames[speakerId] || speakerId,
    };

    setSpeakerNames(nextSpeakerNames);
    writeSpeakerNames(transcriptId, nextSpeakerNames);
  }

  function handleDownloadTranscript(format: "txt" | "srt" | "vtt"): void {
    if (currentSegments.length === 0) {
      return;
    }

    let content = "";
    const mimeType = "text/plain";
    let extension = "txt";

    switch (format) {
      case "srt": {
        content = generateSRT(currentSegments);
        extension = "srt";
        break;
      }
      case "vtt": {
        content = generateVTT(currentSegments);
        extension = "vtt";
        break;
      }
      default: {
        if (showTimestamps || showSpeaker) {
          content = currentSegments
            .map((segment) => {
              if (
                showTimestamps &&
                showSpeaker &&
                segment.speaker &&
                !selectedLanguage
              ) {
                const speakerName =
                  speakerNames[segment.speaker] ?? segment.speaker;

                return `[${formatTimeForDownload(segment.start_time)}] ${speakerName}: ${segment.text}`;
              }

              if (showTimestamps) {
                return `[${formatTimeForDownload(segment.start_time)}] ${segment.text}`;
              }

              if (showSpeaker && segment.speaker) {
                return `${speakerNames[segment.speaker] ?? segment.speaker}: ${segment.text}`;
              }

              return segment.text;
            })
            .join("\n\n");
        } else {
          content = generateTXT(currentSegments);
        }
      }
    }

    downloadFile(content, `transcript.${extension}`, mimeType);
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
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                onClick={() => setMenuOpen(!menuOpen)}
                type="button"
              >
                Export
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
                        handleDownloadTranscript("txt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                    >
                      Download as TXT
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        handleDownloadTranscript("srt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                    >
                      Download as SRT
                    </button>
                    <button
                      className="block w-full rounded-xl px-3 py-2 text-left text-muted-foreground text-sm transition hover:bg-white/5 hover:text-foreground"
                      onClick={() => {
                        handleDownloadTranscript("vtt");
                        setMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                    >
                      Download as VTT
                    </button>
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
            <div className="mt-6 flex justify-end space-x-3">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
                onClick={() => {
                  setShowTranslationModal(false);
                  setPendingLanguage(null);
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
