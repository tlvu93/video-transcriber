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
      className="h-5 w-5 text-green-500"
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
      className="h-5 w-5 animate-spin text-blue-500"
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
  const currentTranscriptData =
    selectedLanguage && translations[selectedLanguage]
      ? translations[selectedLanguage]
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

  if (!transcript) {
    return (
      <div className="rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
        <p className="py-4 text-center text-gray-500 dark:text-gray-400">
          No transcript available.
        </p>
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
    <div className="rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-gray-800 text-lg dark:text-white">
          Transcript{" "}
          {selectedLanguage
            ? `(${
                AVAILABLE_LANGUAGES.find(
                  (language) => language.code === selectedLanguage
                )?.name ?? selectedLanguage
              })`
            : ""}
        </h3>
        <div className="flex items-center space-x-2">
          <button
            className="rounded bg-emerald-500 px-3 py-1 text-sm text-white transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!activeSegment || isLoadingSelectedTranslation}
            onClick={scrollToCurrentSegment}
            type="button"
          >
            Scroll to Current
          </button>
          <div className="relative inline-block text-left">
            <button
              className="flex items-center rounded bg-blue-500 px-3 py-1 text-sm text-white transition-colors hover:bg-blue-600"
              onClick={() => setTranslateMenuOpen(!translateMenuOpen)}
              type="button"
            >
              <GlobeIcon />
              <span className="ml-2">Translate</span>
            </button>
            {translateMenuOpen && (
              <div className="absolute right-0 z-20 mt-2 w-64 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none dark:bg-gray-700">
                <div
                  aria-labelledby="translate-options-menu"
                  aria-orientation="vertical"
                  className="py-1"
                  role="menu"
                >
                  <div className="px-4 py-2 font-semibold text-gray-700 text-sm dark:text-gray-200">
                    Select Language
                  </div>
                  {transcript.language_code && (
                    <button
                      className={`block w-full px-4 py-2 text-left text-sm ${
                        selectedLanguage
                          ? "text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
                          : "bg-gray-100 text-gray-900 dark:bg-gray-600 dark:text-white"
                      }`}
                      onClick={() => {
                        setSelectedLanguage(null);
                        setTranslateMenuOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                    >
                      Show Original ({transcript.language_code.toUpperCase()})
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
                        className={`block flex w-full items-center justify-between px-4 py-2 text-left text-sm ${
                          (isSelected && !isOriginalLanguage) ||
                          (!selectedLanguage && isOriginalLanguage)
                            ? "bg-gray-100 text-gray-900 dark:bg-gray-600 dark:text-white"
                            : "text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
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

          <div className="relative inline-block text-left">
            <button
              className="rounded bg-gray-200 px-3 py-1 text-gray-700 text-sm transition-colors hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              onClick={() => setMenuOpen(!menuOpen)}
              type="button"
            >
              Menu
            </button>
            {menuOpen && (
              <div className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none dark:bg-gray-700">
                <div
                  aria-labelledby="options-menu"
                  aria-orientation="vertical"
                  className="py-1"
                  role="menu"
                >
                  <div className="px-4 py-2 font-semibold text-gray-700 text-sm dark:text-gray-200">
                    Category Options
                  </div>
                  <button
                    className="block w-full px-4 py-2 text-left text-gray-700 text-sm hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
                    onClick={() => setShowTimestamps(!showTimestamps)}
                    role="menuitem"
                    type="button"
                  >
                    {showTimestamps ? "Hide Timestamps" : "Show Timestamps"}
                  </button>
                  <button
                    className="block w-full px-4 py-2 text-left text-gray-700 text-sm hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
                    onClick={() => setShowSpeaker(!showSpeaker)}
                    role="menuitem"
                    type="button"
                  >
                    {showSpeaker ? "Hide Speaker" : "Show Speaker"}
                  </button>
                  <hr className="my-1 border-gray-200 dark:border-gray-600" />
                  <button
                    className="block w-full px-4 py-2 text-left text-gray-700 text-sm hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
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
                    className="block w-full px-4 py-2 text-left text-gray-700 text-sm hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
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
                    className="block w-full px-4 py-2 text-left text-gray-700 text-sm hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-600"
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

      <div className="mb-4">
        <input
          className="w-full rounded-md border border-gray-300 bg-white p-2 text-gray-800 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search transcript..."
          type="text"
          value={searchQuery}
        />
      </div>

      {selectedLanguage && selectedTranslationJob && (
        <div className="mb-4 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-100">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">
              {selectedTranslationJob.status === "completed"
                ? `${getLanguageName(selectedLanguage)} translation ready`
                : `Translating to ${getLanguageName(selectedLanguage)}`}
            </p>
            {selectedTranslationMetrics?.cache_hit && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700 text-xs dark:bg-emerald-900/40 dark:text-emerald-300">
                Cached
              </span>
            )}
            {selectedTranslationDuration && (
              <span className="rounded-full bg-white/80 px-2 py-0.5 font-medium text-sky-800 text-xs dark:bg-sky-900/60 dark:text-sky-100">
                {selectedTranslationDuration}
              </span>
            )}
          </div>
          <p className="mt-1 text-sky-800/90 text-sm dark:text-sky-100/80">
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
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {typeof selectedTranslationMetrics.segment_count === "number" &&
                  selectedTranslationMetrics.segment_count > 0 && (
                    <span className="rounded-full bg-sky-100 px-2 py-1 dark:bg-sky-900/60">
                      {selectedTranslationMetrics.segment_count} segments
                    </span>
                  )}
                {selectedTranslationModelDuration && (
                  <span className="rounded-full bg-sky-100 px-2 py-1 dark:bg-sky-900/60">
                    Model time: {selectedTranslationModelDuration}
                  </span>
                )}
                {selectedTranslationPersistDuration && (
                  <span className="rounded-full bg-sky-100 px-2 py-1 dark:bg-sky-900/60">
                    Save time: {selectedTranslationPersistDuration}
                  </span>
                )}
                {selectedTranslationDetectionDuration &&
                  (selectedTranslationMetrics.language_detection_seconds ?? 0) >
                    0 && (
                    <span className="rounded-full bg-sky-100 px-2 py-1 dark:bg-sky-900/60">
                      Detect: {selectedTranslationDetectionDuration}
                    </span>
                  )}
              </div>
            )}
        </div>
      )}

      <div className="max-h-[500px] overflow-y-auto pr-2">
        {isLoadingSelectedTranslation && (
          <p className="py-4 text-center text-gray-500 dark:text-gray-400">
            Loading translated transcript...
          </p>
        )}
        {!isLoadingSelectedTranslation &&
          currentSegments.length === 0 &&
          currentTranscriptContent && (
            <p className="py-4 text-center text-gray-500 dark:text-gray-400">
              <span className="text-gray-800 dark:text-gray-200">
                {currentTranscriptContent}
              </span>
            </p>
          )}
        {!isLoadingSelectedTranslation &&
          currentSegments.length === 0 &&
          !currentTranscriptContent && (
            <p className="py-4 text-center text-gray-500 dark:text-gray-400">
              No transcript segments available for the selected language.
            </p>
          )}
        {!isLoadingSelectedTranslation &&
          filteredSegments.length > 0 &&
          filteredSegments.map((segment) => (
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

      {showTranslationModal && pendingLanguage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="mx-auto max-w-md rounded-lg bg-white p-6 dark:bg-gray-800">
            <h3 className="mb-4 font-semibold text-gray-800 text-lg dark:text-white">
              Translate Transcript
            </h3>
            <p className="mb-4 text-gray-700 dark:text-gray-300">
              The transcript will be translated to{" "}
              {AVAILABLE_LANGUAGES.find(
                (language) => language.code === pendingLanguage
              )?.name ?? pendingLanguage}
              . This may take a few moments.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                className="rounded bg-gray-200 px-4 py-2 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                onClick={() => {
                  setShowTranslationModal(false);
                  setPendingLanguage(null);
                }}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600"
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
