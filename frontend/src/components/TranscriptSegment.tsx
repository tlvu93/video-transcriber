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
      "border-red-400/20 bg-red-400/10 text-red-200",
      "border-sky-400/20 bg-sky-400/10 text-sky-200",
      "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
      "border-amber-400/20 bg-amber-400/10 text-amber-200",
      "border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-200",
      "border-cyan-400/20 bg-cyan-400/10 text-cyan-200",
      "border-violet-400/20 bg-violet-400/10 text-violet-200",
      "border-orange-400/20 bg-orange-400/10 text-orange-200",
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
      className={`rounded-[1.25rem] border p-3 transition ${
        isActive
          ? "border-primary/35 bg-primary/10 shadow-glow"
          : "border-white/8 bg-white/[0.03] hover:border-white/12 hover:bg-white/[0.06]"
      } ${isEditing ? "" : "cursor-pointer"}`}
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
      <div className="flex items-start gap-3">
        {showTimestamps && (
          <span className="mt-0.5 flex-shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-1 font-mono text-[10px] text-muted-foreground uppercase tracking-[0.16em]">
            {formatTime(safeSegment.start_time)}
          </span>
        )}
        {showSpeaker &&
          safeSegment.speaker &&
          (isEditingSpeaker ? (
            <input
              autoFocus
              className="mt-0.5 w-28 rounded-full border border-primary/35 bg-background px-3 py-1 font-medium text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
              onBlur={handleSpeakerRename}
              onChange={(event) => setSpeakerNameDraft(event.target.value)}
              onClick={(event) => event.stopPropagation()}
              onKeyDown={handleSpeakerKeyDown}
              value={speakerNameDraft}
            />
          ) : (
            <button
              className={`mt-0.5 flex-shrink-0 rounded-full border px-2.5 py-1 font-medium text-xs transition hover:opacity-90 ${getSpeakerColor(
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
            autoFocus
            className="min-h-[40px] w-full flex-1 resize-y rounded-2xl border border-primary/35 bg-background p-3 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            onBlur={handleBlur}
            onChange={(event) => setEditText(event.target.value)}
            onClick={(event) => event.stopPropagation()}
            onDoubleClick={(event) => event.stopPropagation()}
            onKeyDown={handleTextAreaKeyDown}
            rows={1}
            value={editText}
          />
        ) : (
          <span
            className={`flex-1 leading-relaxed ${
              isActive ? "text-foreground" : "text-slate-200"
            }`}
          >
            {safeSegment.text}
          </span>
        )}
      </div>
    </div>
  );
}
