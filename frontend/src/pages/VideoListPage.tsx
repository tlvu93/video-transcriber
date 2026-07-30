import { useQuery } from "@tanstack/react-query";
import {
  startTransition,
  type ReactNode,
  useDeferredValue,
  useEffect,
  useState,
} from "react";
import { fetchVideoListPage } from "../api/videoService";
import { useAppShell } from "../components/AppShellContext";
import LibraryEmptyState from "../components/LibraryEmptyState";
import LibraryControls from "../components/library/LibraryControls";
import LibraryPagination from "../components/library/LibraryPagination";
import SavedViewsPanel from "../components/library/SavedViewsPanel";
import StatCard from "../components/library/StatCard";
import {
  DEFAULT_LIBRARY_PREFERENCES,
  type LibraryPreferences,
  type SavedLibraryView,
} from "../components/library/types";
import VideoTile from "../components/library/VideoTile";
import ProcessingQueue from "../components/ProcessingQueue";
import VideoLibraryTable from "../components/VideoLibraryTable";
import {
  FeedbackPanel,
  LibraryPageSkeleton,
} from "../components/WorkspaceStates";
import { usePersistentState } from "../hooks/usePersistentState";
import { useVideoListLiveUpdates } from "../hooks/useLiveUpdates";

const PAGE_SIZE = 12;
const LIBRARY_PREFERENCES_KEY = "video-transcriber.library-preferences";
const LIBRARY_SAVED_VIEWS_KEY = "video-transcriber.library-saved-views";

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
            <LibraryControls
              hasActiveFilters={hasActiveFilters}
              onReset={resetLibraryPreferences}
              onUpdate={updateLibraryPreferences}
              pageEnd={pageEnd}
              pageStart={pageStart}
              preferences={libraryPreferences}
              totalFilteredVideos={totalFilteredVideos}
            />

            <SavedViewsPanel
              activeSavedViewId={activeSavedViewId}
              onApply={applySavedView}
              onDelete={deleteSavedView}
              onSave={saveCurrentView}
              onSavedViewNameChange={setSavedViewName}
              savedViewName={savedViewName}
              savedViews={savedViews}
            />
          </div>
        ) : null}

        {libraryContent}

        {totalFilteredVideos > PAGE_SIZE ? (
          <LibraryPagination
            onNext={() =>
              setPage((currentPage) => Math.min(totalPages, currentPage + 1))
            }
            onPrevious={() =>
              setPage((currentPage) => Math.max(1, currentPage - 1))
            }
            page={page}
            totalPages={totalPages}
          />
        ) : null}
      </section>
    </div>
  );
}
