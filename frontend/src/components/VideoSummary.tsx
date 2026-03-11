import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { fetchSummariesByTranscriptId } from "../api/videoService";
import type { Summary } from "../types/domain";

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
    // For regular content, split by double newlines or other common separators
    paragraphs = content
      .split(SENTENCE_SPLIT_PATTERN)
      .map((p) => p.trim())
      .filter((p) => p)
      .map((p) => ({ type: "paragraph" as const, text: p }));
  }

  return (
    <div className="text-gray-600 dark:text-gray-300">
      {paragraphs.map((para) => {
        const paragraphKey =
          para.type === "numbered" ? `${para.number}-${para.text}` : para.text;

        if (para.type === "numbered") {
          return (
            <div className="mb-3" key={paragraphKey}>
              <div className="flex">
                <div className="mr-2 font-bold">{para.number}</div>
                <div className="font-semibold">{para.text}</div>
              </div>
              {para.subPoints.length > 0 && (
                <ul className="mt-1 list-disc space-y-1 pl-10">
                  {para.subPoints.map((subPoint) => (
                    <li key={`${paragraphKey}-${subPoint}`}>{subPoint}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        }
        return (
          <p className="mb-3" key={paragraphKey}>
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

export default function VideoSummary({ transcriptId }: VideoSummaryProps) {
  const summaryQuery = useQuery({
    queryKey: ["summaries", transcriptId],
    queryFn: () => fetchSummariesByTranscriptId(transcriptId),
    enabled: Boolean(transcriptId),
    select: (summaries) => summaries[0] ?? null,
  });

  if (summaryQuery.isPending) {
    return (
      <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
        <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
          Summary
        </h2>
        <div className="animate-pulse">
          <div className="mb-2 h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="mb-2 h-4 w-full rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>
    );
  }

  if (summaryQuery.isError) {
    return (
      <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
        <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
          Summary
        </h2>
        <div className="rounded border-red-500 border-l-4 bg-red-100 p-2 text-red-700 dark:bg-red-900/30 dark:text-red-400">
          <p>Failed to load summary. Please try again later.</p>
        </div>
      </div>
    );
  }

  const summary: Summary | null = summaryQuery.data ?? null;

  if (!summary) {
    return (
      <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
        <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
          Summary
        </h2>
        <p className="text-gray-500 italic dark:text-gray-400">
          No summary available for this video.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
      <h2 className="mb-2 font-semibold text-gray-800 text-xl dark:text-white">
        Summary
      </h2>
      <div className="prose dark:prose-invert max-w-none">
        {formatSummaryContent(summary.content)}
      </div>
    </div>
  );
}
