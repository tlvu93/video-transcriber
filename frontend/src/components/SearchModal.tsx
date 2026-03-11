import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { searchTranscripts } from "../api/videoService";

function useDebouncedValue(value: string, delay: number): string {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => window.clearTimeout(timer);
  }, [delay, value]);

  return debouncedValue;
}

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpen: () => void;
}

export default function SearchModal({
  isOpen,
  onClose,
  onOpen,
}: SearchModalProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();
  const debouncedQuery = useDebouncedValue(query, 250);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key === "k";

      if (isShortcut) {
        event.preventDefault();
        onOpen();
        return;
      }

      if (event.key === "Escape" && isOpen) {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, onOpen]);

  useEffect(() => {
    if (isOpen) {
      window.setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
      return;
    }

    setQuery("");
  }, [isOpen]);

  const searchQuery = useQuery({
    queryKey: ["search-modal", debouncedQuery],
    queryFn: () => searchTranscripts(debouncedQuery),
    enabled: isOpen && debouncedQuery.trim().length >= 2,
  });

  function handleResultClick(videoId: string, startTime: number): void {
    navigate(`/videos/${videoId}?t=${startTime}`);
    onClose();
  }

  function formatTime(seconds: number): string {
    if (!seconds) {
      return "00:00";
    }

    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  }

  if (!isOpen) {
    return null;
  }

  const results = searchQuery.data ?? [];
  let modalContent: ReactNode;

  if (!query.trim()) {
    modalContent = (
      <div className="px-6 py-12 text-center">
        <p className="font-semibold text-primary/80 text-sm uppercase tracking-[0.24em]">
          Command search
        </p>
        <h2 className="mt-3 font-semibold text-2xl text-foreground">
          Jump straight to any spoken moment
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Search by topic, phrase, or quote and open the exact video at the
          matching timestamp.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-muted-foreground text-sm">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-2">
            Use <span className="font-mono text-foreground">Cmd/Ctrl + K</span>{" "}
            anytime
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-2">
            Start typing to search all transcripts
          </span>
        </div>
      </div>
    );
  } else if (searchQuery.isFetching) {
    modalContent = (
      <div className="flex items-center justify-center gap-3 px-6 py-14 text-muted-foreground">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary/25 border-t-primary" />
        Searching transcript index...
      </div>
    );
  } else if (searchQuery.isError) {
    modalContent = (
      <div className="px-6 py-10">
        <div className="rounded-[1.25rem] border border-destructive/20 bg-destructive/10 p-4 text-destructive">
          Search failed. Please try again.
        </div>
      </div>
    );
  } else if (results.length === 0) {
    modalContent = (
      <div className="px-6 py-12 text-center">
        <h2 className="font-semibold text-foreground text-xl">
          No matches found
        </h2>
        <p className="mt-3 text-muted-foreground">
          Try a different phrase, broader topic, or a shorter quote.
        </p>
      </div>
    );
  } else {
    modalContent = (
      <div className="space-y-2 p-3">
        {results.map((result) => (
          <button
            className="w-full rounded-[1.25rem] border border-transparent bg-white/[0.02] px-4 py-4 text-left transition hover:border-white/10 hover:bg-white/5"
            key={`${result.transcript_id}-${result.segment_id}-${result.start_time}`}
            onClick={() =>
              handleResultClick(result.video_id, result.start_time)
            }
            type="button"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate font-semibold text-foreground">
                    {result.video_title}
                  </p>
                  {result.speaker ? (
                    <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 font-semibold text-[10px] text-muted-foreground uppercase tracking-[0.18em]">
                      {result.speaker}
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 line-clamp-2 text-muted-foreground text-sm leading-6">
                  {result.text}
                </p>
              </div>
              <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-semibold text-[10px] text-primary uppercase tracking-[0.18em]">
                {formatTime(result.start_time)}
              </div>
            </div>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/70 px-4 pt-20 backdrop-blur-md"
      role="dialog"
    >
      <button
        aria-label="Close search"
        className="absolute inset-0"
        onClick={onClose}
        type="button"
      />

      <div className="panel-elevated relative z-10 w-full max-w-3xl overflow-hidden border-white/10 bg-card/95">
        <div className="border-white/10 border-b px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-muted-foreground">
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
                  d="m21 21-4.35-4.35M18 10.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0z"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <input
              className="w-full bg-transparent text-foreground text-lg outline-none placeholder:text-muted-foreground"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search across all transcripts..."
              ref={inputRef}
              type="text"
              value={query}
            />
            <button
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-medium text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground"
              onClick={onClose}
              type="button"
            >
              Esc
            </button>
          </div>
        </div>

        <div className="max-h-[65vh] overflow-y-auto">{modalContent}</div>

        <div className="border-white/10 border-t px-5 py-3 text-muted-foreground text-xs">
          {results.length > 0 ? (
            <span>
              {results.length} result{results.length === 1 ? "" : "s"} ready to
              open
            </span>
          ) : (
            <span>Search every indexed transcript from one place</span>
          )}
        </div>
      </div>
    </div>
  );
}
