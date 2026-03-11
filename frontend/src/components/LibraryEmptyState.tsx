import type { ReactNode } from "react";

interface LibraryEmptyStateProps {
  action?: ReactNode;
  description: string;
  title: string;
}

export default function LibraryEmptyState({
  action,
  description,
  title,
}: LibraryEmptyStateProps) {
  return (
    <div className="panel-elevated px-6 py-12 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-primary">
        <svg
          aria-hidden="true"
          className="h-8 w-8"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 16V8m0 0-3 3m3-3 3 3M4.5 15.75v1.5A2.25 2.25 0 006.75 19.5h10.5a2.25 2.25 0 002.25-2.25v-1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <h3 className="mt-6 font-semibold text-2xl text-foreground">{title}</h3>
      <p className="mx-auto mt-3 max-w-lg text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
