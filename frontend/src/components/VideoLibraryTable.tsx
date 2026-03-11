import { Link } from "react-router-dom";
import type { Video } from "../types/domain";
import { formatDuration, formatRelativeDate } from "../utils/formatters";
import { getVideoStatusMeta } from "../utils/status";

interface VideoLibraryTableProps {
  videos: Video[];
}

export default function VideoLibraryTable({ videos }: VideoLibraryTableProps) {
  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr className="border-white/5 border-b bg-white/[0.03]">
              <th className="px-5 py-3 text-left font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.2em]">
                Video
              </th>
              <th className="px-5 py-3 text-left font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.2em]">
                Status
              </th>
              <th className="px-5 py-3 text-left font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.2em]">
                Duration
              </th>
              <th className="px-5 py-3 text-left font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.2em]">
                Added
              </th>
              <th className="px-5 py-3 text-right font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.2em]">
                Open
              </th>
            </tr>
          </thead>
          <tbody>
            {videos.map((video) => {
              const statusMeta = getVideoStatusMeta(video.status);

              return (
                <tr
                  className="border-white/5 border-b transition last:border-b-0 hover:bg-white/[0.03]"
                  key={video.id}
                >
                  <td className="px-5 py-4">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-foreground">
                        {video.filename}
                      </p>
                      <p className="mt-1 font-mono text-[11px] text-muted-foreground uppercase tracking-[0.16em]">
                        {video.id.slice(0, 8)}
                      </p>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`status-chip ${statusMeta.badgeClassName}`}
                    >
                      <span className="h-2 w-2 rounded-full bg-current" />
                      {statusMeta.label}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground text-sm">
                    {formatDuration(video.video_metadata?.duration)}
                  </td>
                  <td className="px-5 py-4 text-muted-foreground text-sm">
                    {formatRelativeDate(video.created_at)}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <Link
                      className="inline-flex rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground"
                      to={`/videos/${video.id}`}
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
