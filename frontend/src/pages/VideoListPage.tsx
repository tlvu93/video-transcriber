import { useQuery } from "@tanstack/react-query";
import {
  startTransition,
  type ReactNode,
  useDeferredValue,
  useEffect,
  useState,
} from "react";
import { Link } from "react-router-dom";
import { fetchVideoListPage } from "../api/videoService";
import { useAppShell } from "../components/AppShellContext";
import LibraryEmptyState from "../components/LibraryEmptyState";
import ProcessingQueue from "../components/ProcessingQueue";
import VideoLibraryTable from "../components/VideoLibraryTable";
import {
  FeedbackPanel,
  LibraryPageSkeleton,
} from "../components/WorkspaceStates";
import { usePersistentState } from "../hooks/usePersistentState";
import { useVideoListLiveUpdates } from "../hooks/useLiveUpdates";
import { formatDuration, formatRelativeDate } from "../utils/formatters";
import { getVideoStatusMeta } from "../utils/status";

const PAGE_SIZE = 12;
const LIBRARY_PREFERENCES_KEY = "video-transcriber.library-preferences";
const LIBRARY_SAVED_VIEWS_KEY = "video-transcriber.library-saved-views";

type LibraryDateFilter = "all" | "1" | "7" | "30";
type LibrarySortOrder = "newest" | "oldest" | "name";
type LibraryStatusFilter = "all" | "processing" | "ready" | "failed";
type LibraryViewMode = "card" | "table";

interface LibraryPreferences {
  dateFilter: LibraryDateFilter;
  query: string;
  sortOrder: LibrarySortOrder;
  statusFilter: LibraryStatusFilter;
  viewMode: LibraryViewMode;
}

interface SavedLibraryView extends LibraryPreferences {
  id: string;
  label: string;
}

const DEFAULT_LIBRARY_PREFERENCES: LibraryPreferences = {
  dateFilter: "all",
  query: "",
  sortOrder: "newest",
  statusFilter: "all",
  viewMode: "card",
};

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  tone: string;
  value: number;
}) {
  return (
    <div className="stat-card">
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-br opacity-30 ${tone}`}
      />
      <div className="relative">
        <p className="font-semibold text-muted-foreground text-xs uppercase tracking-[0.24em]">
          {label}
        </p>
        <p className="mt-4 font-semibold text-4xl text-foreground tracking-tight">
          {value}
        </p>
      </div>
    </div>
  );
}

function VideoTile({
  filename,
  id,
  createdAt,
  duration,
  status,
}: {
  createdAt: string;
  duration: number | null | undefined;
  filename: string;
  id: string;
  status: string;
}) {
  const statusMeta = getVideoStatusMeta(status);

  return (
    <Link
      className="group panel relative overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:border-primary/30 hover:shadow-glow"
      to={`/videos/${id}`}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(245,158,11,0.18),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.04),transparent_38%)] opacity-60 transition duration-300 group-hover:opacity-100" />
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <span className={`status-chip ${statusMeta.badgeClassName}`}>
            <span className="h-2 w-2 rounded-full bg-current" />
            {statusMeta.label}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-semibold text-[10px] text-muted-foreground uppercase tracking-[0.18em]">
            {formatRelativeDate(createdAt)}
          </span>
        </div>

        <div className="mt-5 flex aspect-video items-center justify-center rounded-[1.25rem] border border-white/10 bg-[linear-gradient(145deg,rgba(245,158,11,0.12),rgba(15,23,42,0.3)_42%,rgba(56,189,248,0.10))]">
          <div className="flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-slate-950/50 text-primary shadow-lg">
            <svg
              aria-hidden="true"
              className="h-7 w-7"
              fill="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M8 6.82v10.36a1 1 0 001.52.85l8.14-5.18a1 1 0 000-1.7L9.52 5.97A1 1 0 008 6.82z" />
            </svg>
          </div>
        </div>

        <h2 className="mt-5 line-clamp-2 font-semibold text-foreground text-xl tracking-tight">
          {filename}
        </h2>

        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Duration
            </p>
            <p className="mt-2 text-foreground">{formatDuration(duration)}</p>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
            <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
              Video ID
            </p>
            <p className="mt-2 truncate font-mono text-foreground text-xs">
              {id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Added {formatRelativeDate(createdAt)}
          </span>
          <span className="font-medium text-primary transition group-hover:translate-x-1">
            Open workspace
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function VideoListPage() {
  const { openUploadModal } = useAppShell();
  const [libraryPreferences, setLibraryPreferences] =
    usePersistentState<LibraryPreferences>(
      LIBRARY_PREFERENCES_KEY,
      DEFAULT_LIBRARY_PREFERENCES
    );
  const [savedViews, setSavedViews] = usePersistentState<SavedLibraryView[]>(
    LIBRARY_SAVED_VIEWS_KEY,
    []
  );
  const [page, setPage] = useState(1);
  const [savedViewName, setSavedViewName] = useState("");
  const deferredQuery = useDeferredValue(libraryPreferences.query);

  useVideoListLiveUpdates();

  function updateLibraryPreferences(
    patch: Partial<LibraryPreferences>,
    options?: { resetPage?: boolean }
  ): void {
    startTransition(() => {
      setLibraryPreferences((currentPreferences) => ({
        ...currentPreferences,
        ...patch,
      }));
      if (options?.resetPage ?? true) {
        setPage(1);
      }
    });
  }

  function resetLibraryPreferences(): void {
    startTransition(() => {
      setLibraryPreferences(DEFAULT_LIBRARY_PREFERENCES);
      setPage(1);
    });
  }

  function applySavedView(view: SavedLibraryView): void {
    startTransition(() => {
      setLibraryPreferences({
        dateFilter: view.dateFilter,
        query: view.query,
        sortOrder: view.sortOrder,
        statusFilter: view.statusFilter,
        viewMode: view.viewMode,
      });
      setPage(1);
    });
  }

  function saveCurrentView(): void {
    const trimmedLabel = savedViewName.trim();
    const nextView: SavedLibraryView = {
      ...libraryPreferences,
      id:
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      label: trimmedLabel || `Saved view ${savedViews.length + 1}`,
    };

    setSavedViews((currentViews) => [nextView, ...currentViews].slice(0, 8));
    setSavedViewName("");
  }

  function deleteSavedView(viewId: string): void {
    setSavedViews((currentViews) =>
      currentViews.filter((view) => view.id !== viewId)
    );
  }

  const activeSavedViewId =
    savedViews.find((view) => {
      return (
        view.query === libraryPreferences.query &&
        view.statusFilter === libraryPreferences.statusFilter &&
        view.dateFilter === libraryPreferences.dateFilter &&
        view.sortOrder === libraryPreferences.sortOrder &&
        view.viewMode === libraryPreferences.viewMode
      );
    })?.id ?? null;

  const videosQuery = useQuery({
    queryKey: [
      "videos",
      libraryPreferences.statusFilter,
      libraryPreferences.dateFilter,
      libraryPreferences.sortOrder,
      deferredQuery,
      page,
      PAGE_SIZE,
    ],
    queryFn: () =>
      fetchVideoListPage({
        dateWindowDays:
          libraryPreferences.dateFilter === "all"
            ? undefined
            : Number(libraryPreferences.dateFilter),
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        query: deferredQuery.trim() || undefined,
        sort: libraryPreferences.sortOrder,
        statusGroup: libraryPreferences.statusFilter,
      }),
    placeholderData: (previousData) => previousData,
  });
  const processingVideosQuery = useQuery({
    queryKey: ["videos", "processingQueue"],
    queryFn: () =>
      fetchVideoListPage({
        limit: 20,
        offset: 0,
        sort: "newest",
        statusGroup: "processing",
      }),
    select: (pageData) => pageData.items,
  });

  const videos = videosQuery.data?.items ?? [];
  const processingVideos = processingVideosQuery.data ?? [];
  const stats = videosQuery.data?.stats ?? {
    failed_videos: 0,
    processing_videos: 0,
    ready_videos: 0,
    total_videos: 0,
  };
  const totalFilteredVideos = videosQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalFilteredVideos / PAGE_SIZE));
  const pageStart = totalFilteredVideos === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(page * PAGE_SIZE, totalFilteredVideos);
  const hasActiveFilters =
    libraryPreferences.statusFilter !== "all" ||
    libraryPreferences.dateFilter !== "all" ||
    libraryPreferences.sortOrder !== "newest" ||
    libraryPreferences.query.trim().length > 0;

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const libraryContent: ReactNode = (() => {
    if (stats.total_videos === 0) {
      return (
        <LibraryEmptyState
          action={
            <button
              className="rounded-full bg-primary px-5 py-3 font-medium text-primary-foreground transition hover:bg-warning"
              onClick={openUploadModal}
              type="button"
            >
              Add your first video
            </button>
          }
          description="Drop in a local file or import a hosted video URL to kick off the transcription pipeline."
          title="Your library is ready for its first upload"
        />
      );
    }

    if (videos.length === 0) {
      return (
        <LibraryEmptyState
          action={
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-3 font-medium text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
              onClick={resetLibraryPreferences}
              type="button"
            >
              Clear filters
            </button>
          }
          description="Try broadening the status, date, or title filters to see more videos."
          title="No videos match the current view"
        />
      );
    }

    if (libraryPreferences.viewMode === "table") {
      return <VideoLibraryTable videos={videos} />;
    }

    return (
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {videos.map((video) => (
          <VideoTile
            createdAt={video.created_at}
            duration={video.video_metadata?.duration}
            filename={video.filename}
            id={video.id}
            key={video.id}
            status={video.status}
          />
        ))}
      </div>
    );
  })();

  if (videosQuery.isPending) {
    return <LibraryPageSkeleton />;
  }

  if (videosQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <FeedbackPanel
          description="The library could not be loaded right now. Please try again in a moment."
          eyebrow="Error"
          title="Failed to load videos"
          tone="error"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="panel-elevated relative overflow-hidden px-6 py-8 sm:px-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.20),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(56,189,248,0.12),transparent_22%)]" />
        <div className="relative grid gap-8 xl:grid-cols-[1.4fr_0.9fr] xl:items-end">
          <div>
            <span className="status-chip border-primary/20 bg-primary/10 text-primary">
              <span className="h-2 w-2 rounded-full bg-primary" />
              AI Video Intelligence
            </span>
            <h1 className="mt-5 max-w-3xl font-semibold text-4xl text-foreground tracking-tight sm:text-5xl">
              A cinematic dashboard for uploads, transcripts, and summaries.
            </h1>
            <p className="mt-4 max-w-2xl text-base text-muted-foreground leading-7">
              We kept your working backend integrations and layered the new
              generated aesthetic on top: darker surfaces, stronger hierarchy,
              faster scanability, and a clearer workspace feel.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                className="rounded-full bg-primary px-5 py-3 font-medium text-primary-foreground transition hover:bg-warning"
                onClick={openUploadModal}
                type="button"
              >
                Add video
              </button>
              <span className="rounded-full border border-white/10 bg-white/5 px-4 py-3 text-muted-foreground text-sm">
                {stats.total_videos} video{stats.total_videos === 1 ? "" : "s"}{" "}
                tracked
              </span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard
              label="Total videos"
              tone="from-primary/30 via-transparent to-transparent"
              value={stats.total_videos}
            />
            <StatCard
              label="Processing"
              tone="from-info/30 via-transparent to-transparent"
              value={stats.processing_videos}
            />
            <StatCard
              label="Ready"
              tone="from-success/25 via-transparent to-transparent"
              value={stats.ready_videos}
            />
            <StatCard
              label="Needs attention"
              tone="from-destructive/25 via-transparent to-transparent"
              value={stats.failed_videos}
            />
          </div>
        </div>
      </section>

      {processingVideos.length > 0 ? (
        <section className="mt-8">
          <p className="mb-2 font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
            Active Queue
          </p>
          <ProcessingQueue videos={processingVideos} />
        </section>
      ) : null}

      <section className="mt-8">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.24em]">
              Library
            </p>
            <h2 className="mt-2 font-semibold text-2xl text-foreground">
              All videos
            </h2>
          </div>
          <p className="text-muted-foreground text-sm">
            Select a card to open the player, transcript tools, and summary.
          </p>
        </div>

        {stats.total_videos > 0 ? (
          <div className="panel mb-5 space-y-4 p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex rounded-full border border-white/10 bg-white/5 p-1">
                  <button
                    className={`rounded-full px-4 py-2 font-medium text-sm transition ${
                      libraryPreferences.viewMode === "card"
                        ? "bg-primary text-primary-foreground shadow-glow"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                    onClick={() =>
                      updateLibraryPreferences(
                        { viewMode: "card" },
                        { resetPage: false }
                      )
                    }
                    type="button"
                  >
                    Cards
                  </button>
                  <button
                    className={`rounded-full px-4 py-2 font-medium text-sm transition ${
                      libraryPreferences.viewMode === "table"
                        ? "bg-primary text-primary-foreground shadow-glow"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                    onClick={() =>
                      updateLibraryPreferences(
                        { viewMode: "table" },
                        { resetPage: false }
                      )
                    }
                    type="button"
                  >
                    Table
                  </button>
                </div>

                <label className="min-w-[240px] flex-1">
                  <span className="sr-only">Filter by video title</span>
                  <input
                    className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition placeholder:text-muted-foreground focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                    onChange={(event) =>
                      updateLibraryPreferences({ query: event.target.value })
                    }
                    placeholder="Filter by title or filename"
                    type="search"
                    value={libraryPreferences.query}
                  />
                </label>

                <select
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                  onChange={(event) =>
                    updateLibraryPreferences({
                      statusFilter: event.target.value as LibraryStatusFilter,
                    })
                  }
                  value={libraryPreferences.statusFilter}
                >
                  <option value="all">All statuses</option>
                  <option value="processing">Processing</option>
                  <option value="ready">Ready</option>
                  <option value="failed">Failed</option>
                </select>

                <select
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                  onChange={(event) =>
                    updateLibraryPreferences({
                      dateFilter: event.target.value as LibraryDateFilter,
                    })
                  }
                  value={libraryPreferences.dateFilter}
                >
                  <option value="all">All time</option>
                  <option value="1">Last 24 hours</option>
                  <option value="7">Last 7 days</option>
                  <option value="30">Last 30 days</option>
                </select>

                <select
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                  onChange={(event) =>
                    updateLibraryPreferences({
                      sortOrder: event.target.value as LibrarySortOrder,
                    })
                  }
                  value={libraryPreferences.sortOrder}
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                  <option value="name">Name</option>
                </select>

                {hasActiveFilters ? (
                  <button
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                    onClick={resetLibraryPreferences}
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

            <div className="rounded-[1.25rem] border border-white/8 bg-background/30 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
                    Saved views
                  </p>
                  <p className="mt-2 text-muted-foreground text-sm">
                    Save a library setup for review queues, recent uploads, or
                    failure triage.
                  </p>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <input
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm placeholder:text-muted-foreground/80"
                    onChange={(event) => setSavedViewName(event.target.value)}
                    placeholder="Name this view"
                    type="text"
                    value={savedViewName}
                  />
                  <button
                    className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground"
                    onClick={saveCurrentView}
                    type="button"
                  >
                    Save current view
                  </button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                {savedViews.length === 0 ? (
                  <span className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm">
                    No saved views yet
                  </span>
                ) : (
                  savedViews.map((view) => (
                    <div
                      className={`flex items-center gap-2 rounded-full border px-2 py-2 ${
                        view.id === activeSavedViewId
                          ? "border-primary/25 bg-primary/10"
                          : "border-white/10 bg-white/5"
                      }`}
                      key={view.id}
                    >
                      <button
                        className={`rounded-full px-3 py-1 font-medium text-sm transition ${
                          view.id === activeSavedViewId
                            ? "text-primary"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                        onClick={() => applySavedView(view)}
                        type="button"
                      >
                        {view.label}
                      </button>
                      <button
                        aria-label={`Delete saved view ${view.label}`}
                        className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground"
                        onClick={() => deleteSavedView(view.id)}
                        type="button"
                      >
                        Remove
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : null}

        {libraryContent}

        {totalFilteredVideos > PAGE_SIZE ? (
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground text-sm">
              Page {page} of {totalPages}
            </p>
            <div className="flex items-center gap-3">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 font-medium text-sm text-foreground transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                disabled={page >= totalPages}
                onClick={() =>
                  setPage((currentPage) => Math.min(totalPages, currentPage + 1))
                }
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
