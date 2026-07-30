import type {
  LibraryDateFilter,
  LibraryPreferences,
  LibrarySortOrder,
  LibraryStatusFilter,
} from "./types";

interface LibraryControlsProps {
  hasActiveFilters: boolean;
  onReset: () => void;
  onUpdate: (
    patch: Partial<LibraryPreferences>,
    options?: { resetPage?: boolean }
  ) => void;
  pageEnd: number;
  pageStart: number;
  preferences: LibraryPreferences;
  totalFilteredVideos: number;
}

export default function LibraryControls({
  hasActiveFilters,
  onReset,
  onUpdate,
  pageEnd,
  pageStart,
  preferences,
  totalFilteredVideos,
}: LibraryControlsProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-full border border-white/10 bg-white/5 p-1">
          <button
            className={`rounded-full px-4 py-2 font-medium text-sm transition ${
              preferences.viewMode === "card"
                ? "bg-primary text-primary-foreground shadow-glow"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => onUpdate({ viewMode: "card" }, { resetPage: false })}
            type="button"
          >
            Cards
          </button>
          <button
            className={`rounded-full px-4 py-2 font-medium text-sm transition ${
              preferences.viewMode === "table"
                ? "bg-primary text-primary-foreground shadow-glow"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => onUpdate({ viewMode: "table" }, { resetPage: false })}
            type="button"
          >
            Table
          </button>
        </div>

        <label className="min-w-[240px] flex-1">
          <span className="sr-only">Filter by video title</span>
          <input
            className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition placeholder:text-muted-foreground focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
            onChange={(event) => onUpdate({ query: event.target.value })}
            placeholder="Filter by title or filename"
            type="search"
            value={preferences.query}
          />
        </label>

        <select
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
          onChange={(event) =>
            onUpdate({
              statusFilter: event.target.value as LibraryStatusFilter,
            })
          }
          value={preferences.statusFilter}
        >
          <option value="all">All statuses</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
        </select>

        <select
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
          onChange={(event) =>
            onUpdate({
              dateFilter: event.target.value as LibraryDateFilter,
            })
          }
          value={preferences.dateFilter}
        >
          <option value="all">All time</option>
          <option value="1">Last 24 hours</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
        </select>

        <select
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
          onChange={(event) =>
            onUpdate({
              sortOrder: event.target.value as LibrarySortOrder,
            })
          }
          value={preferences.sortOrder}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="name">Name</option>
        </select>

        {hasActiveFilters ? (
          <button
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
            onClick={onReset}
            type="button"
          >
            Reset
          </button>
        ) : null}
      </div>

      <div className="text-muted-foreground text-sm">
        Showing {pageStart}-{pageEnd} of {totalFilteredVideos}
      </div>
    </div>
  );
}
