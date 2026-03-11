import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchVideos } from "../api/videoService";
import { useAppShell } from "../components/AppShellContext";
import LibraryEmptyState from "../components/LibraryEmptyState";
import ProcessingQueue from "../components/ProcessingQueue";
import VideoLibraryTable from "../components/VideoLibraryTable";
import {
  FeedbackPanel,
  LibraryPageSkeleton,
} from "../components/WorkspaceStates";
import { useVideoListLiveUpdates } from "../hooks/useLiveUpdates";
import { formatDuration, formatRelativeDate } from "../utils/formatters";
import { getVideoStatusMeta, isVideoActive } from "../utils/status";
import { sortByNewest } from "../utils/transcript";

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
  const [viewMode, setViewMode] = useState<"card" | "table">("card");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "processing" | "ready" | "failed"
  >("all");
  const [dateFilter, setDateFilter] = useState<"all" | "1" | "7" | "30">("all");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest" | "name">(
    "newest"
  );

  useVideoListLiveUpdates();

  const videosQuery = useQuery({
    queryKey: ["videos"],
    queryFn: fetchVideos,
    select: sortByNewest,
  });

  const videos = videosQuery.data ?? [];
  const processingVideos = videos.filter((video) =>
    isVideoActive(video.status)
  );
  const completedVideos = videos.filter((video) =>
    ["completed", "transcribed"].includes(video.status.toLowerCase())
  );
  const failedVideos = videos.filter((video) =>
    ["error", "failed"].includes(video.status.toLowerCase())
  );

  const filteredVideos = useMemo(() => {
    const now = Date.now();

    const dateFiltered = videos.filter((video) => {
      if (dateFilter === "all") {
        return true;
      }

      const maxAgeMs = Number(dateFilter) * 24 * 60 * 60 * 1000;
      return now - new Date(video.created_at).getTime() <= maxAgeMs;
    });

    const statusFiltered = dateFiltered.filter((video) => {
      const status = video.status.toLowerCase();

      switch (statusFilter) {
        case "processing":
          return ["pending", "processing"].includes(status);
        case "ready":
          return ["completed", "transcribed"].includes(status);
        case "failed":
          return ["failed", "error"].includes(status);
        default:
          return true;
      }
    });

    const sorted = [...statusFiltered];

    if (sortOrder === "name") {
      sorted.sort((left, right) => left.filename.localeCompare(right.filename));
      return sorted;
    }

    sorted.sort((left, right) => {
      const leftTime = new Date(left.created_at).getTime();
      const rightTime = new Date(right.created_at).getTime();
      return sortOrder === "newest"
        ? rightTime - leftTime
        : leftTime - rightTime;
    });

    return sorted;
  }, [dateFilter, sortOrder, statusFilter, videos]);

  const hasActiveFilters =
    statusFilter !== "all" || dateFilter !== "all" || sortOrder !== "newest";

  const libraryContent: ReactNode = (() => {
    if (videos.length === 0) {
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

    if (filteredVideos.length === 0) {
      return (
        <LibraryEmptyState
          action={
            <button
              className="rounded-full border border-white/10 bg-white/5 px-5 py-3 font-medium text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
              onClick={() => {
                setStatusFilter("all");
                setDateFilter("all");
                setSortOrder("newest");
              }}
              type="button"
            >
              Clear filters
            </button>
          }
          description="Try broadening the status or date filters to see more videos."
          title="No videos match the current view"
        />
      );
    }

    if (viewMode === "table") {
      return <VideoLibraryTable videos={filteredVideos} />;
    }

    return (
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {filteredVideos.map((video) => (
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
                {videos.length} video{videos.length === 1 ? "" : "s"} tracked
              </span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard
              label="Total videos"
              tone="from-primary/30 via-transparent to-transparent"
              value={videos.length}
            />
            <StatCard
              label="Processing"
              tone="from-info/30 via-transparent to-transparent"
              value={processingVideos.length}
            />
            <StatCard
              label="Ready"
              tone="from-success/25 via-transparent to-transparent"
              value={completedVideos.length}
            />
            <StatCard
              label="Needs attention"
              tone="from-destructive/25 via-transparent to-transparent"
              value={failedVideos.length}
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

        {videos.length > 0 ? (
          <div className="panel mb-5 flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex rounded-full border border-white/10 bg-white/5 p-1">
                <button
                  className={`rounded-full px-4 py-2 font-medium text-sm transition ${
                    viewMode === "card"
                      ? "bg-primary text-primary-foreground shadow-glow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => setViewMode("card")}
                  type="button"
                >
                  Cards
                </button>
                <button
                  className={`rounded-full px-4 py-2 font-medium text-sm transition ${
                    viewMode === "table"
                      ? "bg-primary text-primary-foreground shadow-glow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => setViewMode("table")}
                  type="button"
                >
                  Table
                </button>
              </div>

              <select
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                onChange={(event) =>
                  setStatusFilter(
                    event.target.value as
                      | "all"
                      | "processing"
                      | "ready"
                      | "failed"
                  )
                }
                value={statusFilter}
              >
                <option value="all">All statuses</option>
                <option value="processing">Processing</option>
                <option value="ready">Ready</option>
                <option value="failed">Failed</option>
              </select>

              <select
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                onChange={(event) =>
                  setDateFilter(event.target.value as "all" | "1" | "7" | "30")
                }
                value={dateFilter}
              >
                <option value="all">All time</option>
                <option value="1">Last 24 hours</option>
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
              </select>

              <select
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                onChange={(event) =>
                  setSortOrder(
                    event.target.value as "newest" | "oldest" | "name"
                  )
                }
                value={sortOrder}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="name">Name</option>
              </select>

              {hasActiveFilters ? (
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                  onClick={() => {
                    setStatusFilter("all");
                    setDateFilter("all");
                    setSortOrder("newest");
                  }}
                  type="button"
                >
                  Reset
                </button>
              ) : null}
            </div>

            <div className="text-muted-foreground text-sm">
              Showing {filteredVideos.length} of {videos.length}
            </div>
          </div>
        ) : null}

        {libraryContent}
      </section>
    </div>
  );
}
