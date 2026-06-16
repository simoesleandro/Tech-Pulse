import { Suspense } from "react";

import { FilterBar } from "@/components/FilterBar";
import { Header } from "@/components/Header";
import { IngestPanel } from "@/components/IngestPanel";
import { NewsFeed } from "@/components/NewsFeed";
import { fetchNews, getFeedItems } from "@/lib/api";
import type { FeedView, NewsItem } from "@/lib/types";

function resolveView(raw?: string): FeedView {
  if (raw === "read" || raw === "saved") {
    return raw;
  }
  return "queue";
}

function FilterBarFallback() {
  return (
    <div className="flex gap-2" aria-hidden="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="h-8 w-16 animate-pulse rounded-md border border-border bg-surface"
        />
      ))}
    </div>
  );
}

function FeedSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="h-[88px] animate-pulse rounded-lg border border-border bg-surface"
        />
      ))}
    </div>
  );
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const params = await searchParams;
  const view = resolveView(params.view);

  let unreadCount = 0;
  let items: NewsItem[] = [];
  let apiError: string | null = null;

  try {
    const [unreadItems, feedItems] = await Promise.all([
      fetchNews({ is_read: false, ai_relevance: "RELEVANTE" }),
      getFeedItems(view),
    ]);
    unreadCount = unreadItems.length;
    items = feedItems;
  } catch {
    apiError =
      "Backend indisponível. Inicie a API em localhost:8000 e recarregue a página.";
  }

  return (
    <>
      <Header unreadCount={unreadCount} />

      <main className="mx-auto max-w-5xl flex-1 px-4 py-6 sm:px-6">
        <div className="flex flex-col gap-6">
          <IngestPanel />

          {apiError ? (
            <div
              className="rounded-lg border border-crimson/40 bg-crimson/10 px-4 py-3 text-sm text-crimson"
              role="alert"
            >
              {apiError}
            </div>
          ) : null}

          <div className="flex flex-col gap-4">
            <Suspense fallback={<FilterBarFallback />}>
              <FilterBar />
            </Suspense>

            {apiError ? (
              <FeedSkeleton />
            ) : (
              <NewsFeed initialItems={items} view={view} />
            )}
          </div>
        </div>
      </main>
    </>
  );
}
