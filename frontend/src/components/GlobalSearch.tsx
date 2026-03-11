import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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

export default function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const debouncedQuery = useDebouncedValue(query, 500);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent): void {
      if (
        dropdownRef.current &&
        event.target instanceof Node &&
        !dropdownRef.current.contains(event.target)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const searchQuery = useQuery({
    queryKey: ["search", debouncedQuery],
    queryFn: () => searchTranscripts(debouncedQuery),
    enabled: debouncedQuery.trim().length >= 2,
  });

  useEffect(() => {
    setShowDropdown(debouncedQuery.trim().length >= 2);
  }, [debouncedQuery]);

  function handleResultClick(videoId: string, startTime: number): void {
    setShowDropdown(false);
    setQuery("");
    navigate(`/videos/${videoId}?t=${startTime}`);
  }

  function formatTime(seconds: number): string {
    if (!seconds) {
      return "00:00";
    }
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  const results = searchQuery.data ?? [];

  function renderResults() {
    if (searchQuery.isError) {
      return (
        <div className="px-4 py-3 text-red-500 text-sm">
          Search failed. Please try again.
        </div>
      );
    }

    if (results.length === 0) {
      return (
        <div className="px-4 py-3 text-gray-500 text-sm dark:text-gray-400">
          No results found for "{query}"
        </div>
      );
    }

    return (
      <ul className="py-1 text-gray-700 text-sm dark:text-gray-200">
        {results.map((result) => (
          <li
            className="border-gray-100 border-b last:border-0 dark:border-gray-700"
            key={`${result.transcript_id}-${result.segment_id}-${result.start_time}`}
          >
            <button
              className="w-full px-4 py-3 text-left hover:bg-gray-100 focus:bg-gray-100 focus:outline-none dark:focus:bg-gray-700 dark:hover:bg-gray-700"
              onClick={() =>
                handleResultClick(result.video_id, result.start_time)
              }
              type="button"
            >
              <div className="mb-1 flex items-baseline justify-between">
                <span className="mr-2 truncate font-semibold">
                  {result.video_title}
                </span>
                <span className="whitespace-nowrap font-mono text-gray-500 text-xs dark:text-gray-400">
                  {formatTime(result.start_time)}
                </span>
              </div>
              <p className="line-clamp-2 text-gray-600 dark:text-gray-300">
                {result.text}
              </p>
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="relative w-full max-w-md" ref={dropdownRef}>
      <div className="relative">
        <input
          className="w-full rounded-full border border-transparent bg-gray-100 px-4 py-2 transition-colors focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search all transcripts..."
          type="text"
          value={query}
        />
        {searchQuery.isFetching && (
          <div className="absolute top-2.5 right-3">
            <svg
              className="h-5 w-5 animate-spin text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <title>Loading</title>
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
          </div>
        )}
      </div>

      {showDropdown && (
        <div className="absolute z-50 mt-2 max-h-96 w-full overflow-y-auto rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 dark:bg-gray-800">
          {renderResults()}
        </div>
      )}
    </div>
  );
}
