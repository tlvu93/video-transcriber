export interface StatusMeta {
  accentClassName: string;
  badgeClassName: string;
  label: string;
}

export function getVideoStatusMeta(status?: string | null): StatusMeta {
  switch (status?.toLowerCase()) {
    case "completed":
    case "transcribed": {
      return {
        label: "Ready",
        badgeClassName:
          "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
        accentClassName: "text-emerald-300",
      };
    }
    case "pending": {
      return {
        label: "Queued",
        badgeClassName: "border-amber-400/20 bg-amber-400/10 text-amber-100",
        accentClassName: "text-amber-200",
      };
    }
    case "processing": {
      return {
        label: "Processing",
        badgeClassName: "border-sky-400/20 bg-sky-400/10 text-sky-100",
        accentClassName: "text-sky-200",
      };
    }
    case "error":
    case "failed": {
      return {
        label: "Failed",
        badgeClassName: "border-red-400/20 bg-red-400/10 text-red-200",
        accentClassName: "text-red-200",
      };
    }
    default: {
      return {
        label: "Unknown",
        badgeClassName: "border-white/10 bg-white/5 text-slate-200",
        accentClassName: "text-slate-200",
      };
    }
  }
}

export function isVideoActive(status?: string | null): boolean {
  return ["pending", "processing"].includes(status?.toLowerCase() ?? "");
}

export function getStatusColor(status?: string | null): string {
  return getVideoStatusMeta(status).accentClassName;
}
