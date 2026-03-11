import type { KeyboardEvent, MouseEvent } from "react";
import { useEffect, useState } from "react";
import type { TranscriptSegment as TranscriptSegmentType } from "../types/domain";

interface TranscriptSegmentProps {
  isActive: boolean;
  isEditable?: boolean;
  onClick: (time: number) => void;
  onEdit?: (segmentId: number, newText: string) => void;
  onRenameSpeaker?: (speakerId: string, newName: string) => void;
  segment: TranscriptSegmentType;
  showSpeaker: boolean;
  showTimestamps: boolean;
  speakerName?: string;
}

export default function TranscriptSegment({
  segment,
  isActive,
  showTimestamps,
  showSpeaker,
  onClick,
  onEdit,
  onRenameSpeaker,
  speakerName,
  isEditable = false,
}: TranscriptSegmentProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isEditingSpeaker, setIsEditingSpeaker] = useState(false);
  const [editText, setEditText] = useState(segment?.text || "");
  const [speakerNameDraft, setSpeakerNameDraft] = useState(speakerName ?? "");

  useEffect(() => {
    setEditText(segment?.text || "");
  }, [segment?.text]);

  useEffect(() => {
    setSpeakerNameDraft(speakerName ?? "");
  }, [speakerName]);

  function formatTime(seconds: number | undefined | null): string {
    if (seconds === undefined || seconds === null) {
      return "00:00";
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
  }

  const safeSegment = {
    id: segment.id || 0,
    start_time: segment.start_time || 0,
    end_time: segment.end_time || 0,
    text: segment.text || "",
    speaker: segment.speaker || null,
  };

  function getSpeakerColor(speaker?: string | null): string | null {
    if (!speaker) {
      return null;
    }

    const colors = [
      "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
      "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
      "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
      "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
      "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    ];

    const speakerNum = Number.parseInt(speaker.replace(/\D/g, ""), 10) || 0;
    return colors[speakerNum % colors.length] ?? colors[0] ?? null;
  }

  function handleDoubleClick(event: MouseEvent<HTMLDivElement>): void {
    if (!isEditable) {
      return;
    }
    event.stopPropagation();
    setIsEditing(true);
  }

  function handleBlur(): void {
    setIsEditing(false);
    if (editText !== safeSegment.text && onEdit) {
      onEdit(safeSegment.id, editText);
    }
  }

  function handleTextAreaKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>
  ): void {
    if (event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.blur();
    } else if (event.key === "Escape") {
      setEditText(safeSegment.text);
      setIsEditing(false);
    }
  }

  function handleSpeakerRename(): void {
    if (!(safeSegment.speaker && onRenameSpeaker)) {
      setIsEditingSpeaker(false);
      return;
    }

    onRenameSpeaker(safeSegment.speaker, speakerNameDraft);
    setIsEditingSpeaker(false);
  }

  function handleSpeakerKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSpeakerRename();
    } else if (event.key === "Escape") {
      setSpeakerNameDraft(speakerName ?? "");
      setIsEditingSpeaker(false);
    }
  }

  return (
    <div
      className={`mb-1 rounded-md p-2 transition-colors ${
        isActive
          ? "border-blue-500 border-l-4 bg-blue-100 dark:bg-blue-900"
          : "hover:bg-gray-100 dark:hover:bg-gray-700"
      } ${!isEditing && "cursor-pointer"}`}
      onClick={() => {
        if (!isEditing) {
          onClick(safeSegment.start_time);
        }
      }}
      onDoubleClick={handleDoubleClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" && !isEditing) {
          onClick(safeSegment.start_time);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-start gap-2">
        {showTimestamps && (
          <span className="mt-1 flex-shrink-0 cursor-pointer font-mono text-gray-500 text-xs dark:text-gray-400">
            [{formatTime(safeSegment.start_time)}]
          </span>
        )}
        {showSpeaker &&
          safeSegment.speaker &&
          (isEditingSpeaker ? (
            <input
              autoFocus
              className="mt-1 w-28 rounded-full border border-blue-500 bg-white px-2 py-1 font-medium text-gray-900 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              onBlur={handleSpeakerRename}
              onChange={(event) => setSpeakerNameDraft(event.target.value)}
              onClick={(event) => event.stopPropagation()}
              onKeyDown={handleSpeakerKeyDown}
              value={speakerNameDraft}
            />
          ) : (
            <button
              className={`mt-1 flex-shrink-0 rounded-full px-2 py-1 font-medium text-xs transition hover:opacity-90 ${getSpeakerColor(
                safeSegment.speaker
              )}`}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setIsEditingSpeaker(true);
              }}
              title="Rename speaker"
              type="button"
            >
              {speakerName ?? safeSegment.speaker}
            </button>
          ))}
        {isEditing ? (
          <textarea
            autoFocus // Needed for inline editing UX to be smooth
            className="min-h-[40px] w-full flex-1 resize-y rounded border border-blue-500 bg-white p-1 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            onBlur={handleBlur}
            onChange={(event) => setEditText(event.target.value)}
            onClick={(event) => event.stopPropagation()}
            onDoubleClick={(event) => event.stopPropagation()}
            onKeyDown={handleTextAreaKeyDown}
            rows={1}
            value={editText}
          />
        ) : (
          <span className="flex-1 text-gray-800 leading-relaxed dark:text-gray-200">
            {safeSegment.text}
          </span>
        )}
      </div>
    </div>
  );
}
