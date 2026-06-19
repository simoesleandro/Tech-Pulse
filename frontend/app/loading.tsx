export default function Loading() {
  return (
    <>
      <header className="border-b border-border bg-surface/80 backdrop-blur-sm">
        <div className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
          <div className="h-4 w-40 animate-pulse rounded bg-surface" />
          <div className="mt-3 h-8 w-56 animate-pulse rounded bg-surface" />
        </div>
      </header>

      <main className="mx-auto max-w-5xl flex-1 px-4 py-6 sm:px-6">
        <div className="flex flex-col gap-6">
          <div className="h-28 animate-pulse rounded-lg border border-border bg-surface" />
          <div className="flex gap-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className="h-8 w-16 animate-pulse rounded-md border border-border bg-surface"
              />
            ))}
          </div>
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className="h-[88px] animate-pulse rounded-lg border border-border bg-surface"
              />
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
