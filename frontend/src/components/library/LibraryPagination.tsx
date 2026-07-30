interface LibraryPaginationProps {
  onNext: () => void;
  onPrevious: () => void;
  page: number;
  totalPages: number;
}

export default function LibraryPagination({
  onNext,
  onPrevious,
  page,
  totalPages,
}: LibraryPaginationProps) {
  return (
    <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-muted-foreground text-sm">
        Page {page} of {totalPages}
      </p>
      <div className="flex items-center gap-3">
        <button
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 font-medium text-sm text-foreground transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={page <= 1}
          onClick={onPrevious}
          type="button"
        >
          Previous
        </button>
        <button
          className="rounded-full border border-primary/25 bg-primary/10 px-4 py-2 font-medium text-primary text-sm transition hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          disabled={page >= totalPages}
          onClick={onNext}
          type="button"
        >
          Next
        </button>
      </div>
    </div>
  );
}
