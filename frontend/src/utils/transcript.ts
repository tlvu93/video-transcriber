import type {
  Transcript,
  TranscriptSegment,
  TranslatedTranscript,
} from "../types/domain";

function normalizeSegment(
  segment: Partial<TranscriptSegment> | null | undefined,
  index: number
): TranscriptSegment {
  return {
    id: segment?.id ?? index + 1,
    start_time: segment?.start_time ?? 0,
    end_time: segment?.end_time ?? 0,
    text: segment?.text ?? "",
    speaker: segment?.speaker ?? null,
  };
}

function buildFallbackSegments(content: string): TranscriptSegment[] {
  if (!content) {
    return [];
  }

  return [
    {
      id: 1,
      start_time: 0,
      end_time: 0,
      text: content,
      speaker: null,
    },
  ];
}

export function normalizeTranscript(
  transcript: Transcript | null | undefined
): Transcript | null {
  if (!transcript) {
    return null;
  }

  const segments =
    transcript.segments?.map((segment, index) =>
      normalizeSegment(segment, index)
    ) ?? buildFallbackSegments(transcript.content);

  return {
    ...transcript,
    segments,
  };
}

export function normalizeTranslatedTranscript(
  transcript: TranslatedTranscript | null | undefined
): TranslatedTranscript | null {
  if (!transcript) {
    return null;
  }

  return {
    ...transcript,
    segments:
      transcript.segments?.map((segment, index) =>
        normalizeSegment(segment, index)
      ) ?? [],
  };
}

export function sortByNewest<T extends { created_at: string }>(
  items: T[]
): T[] {
  return [...items].sort(
    (left, right) =>
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );
}
