import type { SavedLibraryView } from "./types";

interface SavedViewsPanelProps {
  activeSavedViewId: string | null;
  onApply: (view: SavedLibraryView) => void;
  onDelete: (viewId: string) => void;
  onSave: () => void;
  onSavedViewNameChange: (value: string) => void;
  savedViewName: string;
  savedViews: SavedLibraryView[];
}

export default function SavedViewsPanel({
  activeSavedViewId,
  onApply,
  onDelete,
  onSave,
  onSavedViewNameChange,
  savedViewName,
  savedViews,
}: SavedViewsPanelProps) {
  return (
    <div className="rounded-[1.25rem] border border-white/8 bg-background/30 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
            Saved views
          </p>
          <p className="mt-2 text-muted-foreground text-sm">
            Save a library setup for review queues, recent uploads, or failure
            triage.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-foreground text-sm placeholder:text-muted-foreground/80"
            onChange={(event) => onSavedViewNameChange(event.target.value)}
            placeholder="Name this view"
            type="text"
            value={savedViewName}
          />
          <button
            className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground"
            onClick={onSave}
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
                onClick={() => onApply(view)}
                type="button"
              >
                {view.label}
              </button>
              <button
                aria-label={`Delete saved view ${view.label}`}
                className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-muted-foreground text-xs transition hover:bg-white/10 hover:text-foreground"
                onClick={() => onDelete(view.id)}
                type="button"
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
