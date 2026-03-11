import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchTranslatedTranscripts } from "../api/videoService";
import type { Transcript, Video } from "../types/domain";
import {
  formatDuration,
  formatFullDate,
  humanizeStatus,
} from "../utils/formatters";
import { getVideoStatusMeta } from "../utils/status";
import { normalizeTranslatedTranscript } from "../utils/transcript";

interface VideoMetadataProps {
  onRetryTranscription?: (() => Promise<unknown>) | null;
  transcript?: Transcript | null;
  video: Video | null;
}

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
      <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
        {label}
      </p>
      <p className="mt-2 text-foreground text-sm">{value}</p>
    </div>
  );
}

function getSpeakerIds(transcript: Transcript | null | undefined) {
  const speakerIds: string[] = [];

  for (const segment of transcript?.segments ?? []) {
    if (segment.speaker && !speakerIds.includes(segment.speaker)) {
      speakerIds.push(segment.speaker);
    }
  }

  return speakerIds;
}

function formatLanguage(languageCode: string | null | undefined) {
  return languageCode ? languageCode.toUpperCase() : "Unknown";
}

function formatCount(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export default function VideoMetadata({
  video,
  onRetryTranscription,
  transcript,
}: VideoMetadataProps) {
  const [retrying, setRetrying] = useState(false);
  const transcriptId = transcript?.id ?? "";
  const translatedTranscriptsQuery = useQuery({
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
  const speakerIds = getSpeakerIds(transcript);
  const translatedLanguages = (translatedTranscriptsQuery.data ?? []).map(
    (translation) => translation.language.toUpperCase()
  );

  if (!video) {
    return (
      <div className="panel p-5">
        <p className="text-muted-foreground">Loading metadata...</p>
      </div>
    );
  }

  const statusMeta = getVideoStatusMeta(video.status);
  const detailItems = [
    {
      label: "Uploaded",
      value: formatFullDate(video.created_at),
    },
    {
      label: "Duration",
      value: formatDuration(video.video_metadata?.duration),
    },
    {
      label: "Language",
      value: formatLanguage(transcript?.language_code),
    },
    {
      label: "Segments",
      value: `${transcript?.segments?.length ?? 0}`,
    },
    {
      label: "Speakers",
      value: speakerIds.length > 0 ? `${speakerIds.length}` : "None",
    },
    {
      label: "Fingerprint",
      value: (video.file_hash ?? video.id).slice(0, 12),
    },
  ];

  async function handleRetry(): Promise<void> {
    if (!onRetryTranscription || retrying) {
      return;
    }

    try {
      setRetrying(true);
      await onRetryTranscription();
    } catch (error) {
      console.error("Error retrying transcription:", error);
    } finally {
      setRetrying(false);
    }
  }

  return (
    <section className="panel overflow-hidden">
      <div className="border-white/10 border-b px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
              Video details
            </p>
            <h2 className="mt-2 font-semibold text-2xl text-foreground tracking-tight">
              {video.filename}
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className={`status-chip ${statusMeta.badgeClassName}`}>
              <span className="h-2 w-2 rounded-full bg-current" />
              {humanizeStatus(video.status)}
            </span>

            {onRetryTranscription && (
              <button
                className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                disabled={retrying}
                onClick={handleRetry}
                type="button"
              >
                {retrying ? "Retrying..." : "Retry transcription"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-5 sm:grid-cols-2">
        {detailItems.map((item) => (
          <MetadataItem
            key={item.label}
            label={item.label}
            value={item.value}
          />
        ))}
      </div>

      {speakerIds.length > 0 && (
        <div className="border-white/10 border-t px-5 py-4">
          <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
            Speakers
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {speakerIds.map((speakerId, index) => (
              <span
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-medium text-foreground text-xs"
                key={speakerId}
              >
                Speaker {index + 1}
              </span>
            ))}
          </div>
        </div>
      )}

      {transcriptId && (
        <div className="border-white/10 border-t px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Available translations
            </p>
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 font-medium text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              {translatedLanguages.length > 0
                ? formatCount(translatedLanguages.length, "language")
                : "None yet"}
            </span>
          </div>

          {translatedTranscriptsQuery.isPending && (
            <p className="mt-3 text-muted-foreground text-sm">
              Checking translation availability...
            </p>
          )}

          {!translatedTranscriptsQuery.isPending &&
            translatedLanguages.length === 0 && (
              <p className="mt-3 text-muted-foreground text-sm">
                Request a translated transcript from the transcript panel when
                you need another language.
              </p>
            )}

          {translatedLanguages.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {translatedLanguages.map((language) => (
                <span
                  className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-medium text-primary text-xs"
                  key={language}
                >
                  {language}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
