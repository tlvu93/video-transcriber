import type { ReactNode } from "react";

function SkeletonBlock({ className }: { className: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-2xl bg-white/8 ${className}`}
    />
  );
}

export function FeedbackPanel({
  action,
  className = "",
  description,
  eyebrow,
  title,
  tone = "default",
}: {
  action?: ReactNode;
  className?: string;
  description: string;
  eyebrow: string;
  title: string;
  tone?: "default" | "error";
}) {
  const toneClassName =
    tone === "error"
      ? "border-destructive/20 bg-destructive/10"
      : "border-white/10 bg-card/80";
  const eyebrowClassName =
    tone === "error" ? "text-destructive/80" : "text-primary/80";

  return (
    <div className={`panel-elevated p-8 ${toneClassName} ${className}`.trim()}>
      <p
        className={`font-semibold text-xs uppercase tracking-[0.24em] ${eyebrowClassName}`}
      >
        {eyebrow}
      </p>
      <h2 className="mt-3 font-semibold text-2xl text-foreground">{title}</h2>
      <p className="mt-3 max-w-2xl text-muted-foreground leading-7">
        {description}
      </p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function LibraryPageSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="panel-elevated relative overflow-hidden px-6 py-8 sm:px-8">
        <div className="grid gap-8 xl:grid-cols-[1.4fr_0.9fr] xl:items-end">
          <div>
            <SkeletonBlock className="h-7 w-40 rounded-full" />
            <SkeletonBlock className="mt-5 h-14 w-full max-w-3xl" />
            <SkeletonBlock className="mt-3 h-14 w-5/6 max-w-2xl" />
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <SkeletonBlock className="h-12 w-32 rounded-full" />
              <SkeletonBlock className="h-12 w-40 rounded-full" />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {[0, 1, 2, 3].map((index) => (
              <div className="stat-card" key={index}>
                <SkeletonBlock className="h-4 w-24" />
                <SkeletonBlock className="mt-4 h-10 w-16" />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-8">
        <SkeletonBlock className="mb-4 h-4 w-28" />
        <div className="panel grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <div
              className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-5"
              key={index}
            >
              <div className="flex items-center justify-between gap-3">
                <SkeletonBlock className="h-6 w-24 rounded-full" />
                <SkeletonBlock className="h-6 w-16 rounded-full" />
              </div>
              <SkeletonBlock className="mt-5 aspect-video w-full" />
              <SkeletonBlock className="mt-5 h-7 w-4/5" />
              <div className="mt-4 grid grid-cols-2 gap-3">
                <SkeletonBlock className="h-16 w-full" />
                <SkeletonBlock className="h-16 w-full" />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <SkeletonBlock className="h-4 w-16" />
            <SkeletonBlock className="mt-3 h-8 w-40" />
          </div>
          <SkeletonBlock className="h-4 w-72" />
        </div>

        <div className="panel mt-5 flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-3">
            <SkeletonBlock className="h-11 w-44 rounded-full" />
            <SkeletonBlock className="h-11 w-36 rounded-full" />
            <SkeletonBlock className="h-11 w-36 rounded-full" />
            <SkeletonBlock className="h-11 w-36 rounded-full" />
          </div>
          <SkeletonBlock className="h-4 w-32" />
        </div>

        <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <div className="panel p-5" key={index}>
              <div className="flex items-start justify-between gap-3">
                <SkeletonBlock className="h-6 w-24 rounded-full" />
                <SkeletonBlock className="h-6 w-20 rounded-full" />
              </div>
              <SkeletonBlock className="mt-5 aspect-video w-full" />
              <SkeletonBlock className="mt-5 h-7 w-4/5" />
              <div className="mt-4 grid grid-cols-2 gap-3">
                <SkeletonBlock className="h-16 w-full" />
                <SkeletonBlock className="h-16 w-full" />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function SummaryPanelSkeleton() {
  return (
    <section className="panel overflow-hidden">
      <div className="border-white/10 border-b px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <SkeletonBlock className="h-4 w-20" />
            <SkeletonBlock className="mt-3 h-7 w-36" />
          </div>
          <div className="flex gap-2">
            <SkeletonBlock className="h-9 w-24 rounded-full" />
            <SkeletonBlock className="h-9 w-28 rounded-full" />
          </div>
        </div>
      </div>
      <div className="space-y-3 p-5">
        <SkeletonBlock className="h-5 w-4/5" />
        <SkeletonBlock className="h-5 w-full" />
        <SkeletonBlock className="h-5 w-5/6" />
        <SkeletonBlock className="h-5 w-11/12" />
      </div>
    </section>
  );
}

export function VideoWorkspaceSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <SkeletonBlock className="h-5 w-36" />
          <SkeletonBlock className="mt-4 h-11 w-[min(34rem,90vw)] max-w-full" />
          <SkeletonBlock className="mt-3 h-5 w-40" />
        </div>
        <SkeletonBlock className="h-8 w-28 rounded-full" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.9fr)]">
        <div className="space-y-6">
          <div className="panel overflow-hidden p-4">
            <SkeletonBlock className="aspect-video w-full rounded-[1.25rem]" />
          </div>
          <SummaryPanelSkeleton />
        </div>

        <div className="flex flex-col gap-6">
          <div className="panel p-5">
            <SkeletonBlock className="h-4 w-24" />
            <SkeletonBlock className="mt-3 h-8 w-3/4" />
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((index) => (
                <SkeletonBlock className="h-16 w-full" key={index} />
              ))}
            </div>
          </div>

          <div className="panel p-5">
            <SkeletonBlock className="h-4 w-20" />
            <div className="mt-5 space-y-5">
              {[0, 1, 2, 3].map((index) => (
                <div className="flex gap-4" key={index}>
                  <SkeletonBlock className="h-10 w-10 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <SkeletonBlock className="h-4 w-28" />
                    <SkeletonBlock className="h-5 w-full" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel flex-1 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <SkeletonBlock className="h-4 w-20" />
                <SkeletonBlock className="mt-3 h-7 w-40" />
              </div>
              <div className="flex gap-2">
                <SkeletonBlock className="h-10 w-28 rounded-full" />
                <SkeletonBlock className="h-10 w-24 rounded-full" />
              </div>
            </div>

            <SkeletonBlock className="mt-5 h-12 w-full rounded-full" />

            <div className="mt-5 space-y-3">
              {[0, 1, 2, 3, 4].map((index) => (
                <div
                  className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4"
                  key={index}
                >
                  <div className="flex gap-2">
                    <SkeletonBlock className="h-6 w-14 rounded-full" />
                    <SkeletonBlock className="h-6 w-24 rounded-full" />
                  </div>
                  <SkeletonBlock className="mt-3 h-5 w-full" />
                  <SkeletonBlock className="mt-2 h-5 w-4/5" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
