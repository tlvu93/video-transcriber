import { useAppShell } from "./AppShellContext";

interface GlobalSearchProps {
  compact?: boolean;
}

export default function GlobalSearch({ compact = false }: GlobalSearchProps) {
  const { openSearchModal } = useAppShell();

  if (compact) {
    return (
      <button
        aria-label="Open search"
        className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
        onClick={openSearchModal}
        type="button"
      >
        <svg
          aria-hidden="true"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="m21 21-4.35-4.35M18 10.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    );
  }

  return (
    <button
      className="flex w-full items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
      onClick={openSearchModal}
      type="button"
    >
      <svg
        aria-hidden="true"
        className="h-4 w-4 flex-shrink-0 text-muted-foreground"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="m21 21-4.35-4.35M18 10.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0z"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="flex-1 text-muted-foreground text-sm">
        Search transcripts, moments, and clips...
      </span>
      <span className="hidden rounded-full border border-white/10 bg-white/5 px-2 py-1 font-mono font-semibold text-[10px] text-muted-foreground uppercase tracking-[0.2em] lg:inline-flex">
        Cmd K
      </span>
    </button>
  );
}
