export function formatDuration(seconds?: number | null): string {
  if (!seconds || Number.isNaN(seconds)) {
    return "Unknown";
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
  }

  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

export function formatRelativeDate(input?: string | null): string {
  if (!input) {
    return "Unknown";
  }

  const date = new Date(input);
  const deltaMs = Date.now() - date.getTime();

  if (Number.isNaN(deltaMs)) {
    return "Unknown";
  }

  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (deltaMs < hour) {
    const minutes = Math.max(1, Math.round(deltaMs / minute));
    return `${minutes}m ago`;
  }

  if (deltaMs < day) {
    const hours = Math.round(deltaMs / hour);
    return `${hours}h ago`;
  }

  if (deltaMs < 7 * day) {
    const days = Math.round(deltaMs / day);
    return `${days}d ago`;
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year:
      date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
  });
}

export function formatFullDate(input?: string | null): string {
  if (!input) {
    return "Unknown date";
  }

  const date = new Date(input);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function humanizeStatus(status?: string | null): string {
  if (!status) {
    return "Unknown";
  }

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
