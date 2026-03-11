import { Link } from "react-router-dom";
import type { Video } from "../types/domain";
import { formatDuration, formatRelativeDate } from "../utils/formatters";
import { getVideoStatusMeta } from "../utils/status";

interface ProcessingQueueProps {
  videos: Video[];
}

const statusPriority: Record<string, number> = {
  processing: 0,
  pending: 1,
  completed: 2,
  failed: 3,
  error: 3,
  transcribed: 2,
};

export default function ProcessingQueue({ videos }: ProcessingQueueProps) {
  if (videos.length === 0) {
    return null;
  }

  const sortedVideos = [...videos].sort((left, right) => {
    const leftPriority =
      statusPriority[left.status.toLowerCase()] ?? Number.MAX_SAFE_INTEGER;
    const rightPriority =
      statusPriority[right.status.toLowerCase()] ?? Number.MAX_SAFE_INTEGER;

    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }

    return (
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    );
  });

  const counts = {
    pending: sortedVideos.filter((video) => video.status === "pending").length,
    processing: sortedVideos.filter((video) => video.status === "processing")
      .length,
  };

  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-semibold text-2xl text-foreground">
          Processing queue
        </h2>
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 font-semibold text-primary text-sm">
          {videos.length}
        </span>
      </div>

      <div className="panel overflow-hidden">
        {sortedVideos.map((video, index) => {
          const statusMeta = getVideoStatusMeta(video.status);

          return (
            <Link
              className={`flex flex-col gap-4 px-5 py-4 transition hover:bg-white/5 sm:flex-row sm:items-center sm:justify-between ${
                index < sortedVideos.length - 1 ? "border-white/5 border-b" : ""
              }`}
              key={video.id}
              to={`/videos/${video.id}`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-3">
                  <span className={`status-chip ${statusMeta.badgeClassName}`}>
                    <span className="h-2 w-2 animate-pulse rounded-full bg-current" />
                    {statusMeta.label}
                  </span>
                  <span className="text-muted-foreground text-sm">
                    Added {formatRelativeDate(video.created_at)}
                  </span>
                </div>
                <h3 className="mt-3 truncate font-semibold text-foreground text-lg">
                  {video.filename}
                </h3>
                <div className="indeterminate-bar mt-3" />
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-right text-muted-foreground text-sm">
                <div>{formatDuration(video.video_metadata?.duration)}</div>
                <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.16em]">
                  {video.id.slice(0, 8)}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="panel px-4 py-3">
          <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
            Actively processing
          </p>
          <p className="mt-2 font-semibold text-3xl text-foreground">
            {counts.processing}
          </p>
        </div>
        <div className="panel px-4 py-3">
          <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
            Waiting in queue
          </p>
          <p className="mt-2 font-semibold text-3xl text-foreground">
            {counts.pending}
          </p>
        </div>
      </div>
    </section>
  );
}
