import { Link } from "react-router-dom";
import { formatDuration, formatRelativeDate } from "../../utils/formatters";
import { getVideoStatusMeta } from "../../utils/status";

interface VideoTileProps {
  createdAt: string;
  duration: number | null | undefined;
  filename: string;
  id: string;
  status: string;
}

export default function VideoTile({
  createdAt,
  duration,
  filename,
  id,
  status,
}: VideoTileProps) {
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
