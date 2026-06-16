import { Suspense } from "react";

import { FilterBar } from "@/components/FilterBar";
import { FolderPanel } from "@/components/FolderPanel";
import { Header } from "@/components/Header";
import { IngestPanel } from "@/components/IngestPanel";
import { NewsFeed } from "@/components/NewsFeed";
import { ObsidianStatusBanner } from "@/components/ObsidianStatusBanner";
import { fetchFolders, getFeedPage, getUnreadCount } from "@/lib/api";
import type { FeedView, TopicFolder } from "@/lib/types";

function resolveView(raw?: string): FeedView {
  if (raw === "read" || raw === "saved") {
    return raw;
  }
  return "queue";
}

function FilterBarFallback() {
  return (
    <div className="flex gap-2" aria-hidden="true">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="h-8 w-16 animate-pulse rounded-md border border-border bg-surface"
        />
      ))}
    </div>
  );
}

function FolderPanelFallback() {
  return (
    <div
      className="h-24 animate-pulse rounded-lg border border-border bg-surface"
      aria-hidden="true"
    />
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
  searchParams: Promise<{
    view?: string;
    folder?: string;
    page?: string;
    source?: string;
    hype?: string;
    q?: string;
  }>;
}) {
  const params = await searchParams;
  const view = resolveView(params.view);
  const folderId = params.folder ? Number(params.folder) : undefined;
  const page = params.page ? Math.max(1, Number(params.page)) : 1;
  const source = params.source || undefined;
  const hype = params.hype !== undefined && params.hype !== "" ? Number(params.hype) : undefined;
  const q = params.q?.trim() || undefined;

  let unreadCount = 0;
  let feedTotal = 0;
  let items = [] as Awaited<ReturnType<typeof getFeedPage>>["items"];
  let folders: TopicFolder[] = [];
  let apiError: string | null = null;
  let foldersError: string | null = null;

  try {
    unreadCount = await getUnreadCount();
  } catch {
    apiError =
      "Backend indisponível. Inicie a API em localhost:8000 e recarregue a página.";
  }

  if (!apiError) {
    try {
      const feed = await getFeedPage({
        view,
        folderId,
        page,
        source,
        hype,
        q,
      });
      items = feed.items;
      feedTotal = feed.total;
    } catch {
      apiError =
        "Backend indisponível. Inicie a API em localhost:8000 e recarregue a página.";
    }
  }

  try {
    folders = await fetchFolders();
  } catch {
    foldersError =
      "Não foi possível carregar as pastas. Reinicie o backend com o código mais recente.";
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

          {foldersError ? (
            <div
              className="rounded-lg border border-crimson/30 bg-crimson/5 px-4 py-2 text-xs text-crimson"
              role="alert"
            >
              {foldersError}
            </div>
          ) : null}

          <div className="flex flex-col gap-4">
            <Suspense fallback={<FilterBarFallback />}>
              <FilterBar />
            </Suspense>

            <Suspense fallback={<FolderPanelFallback />}>
              <FolderPanel folders={folders} />
            </Suspense>

            <ObsidianStatusBanner />

            {apiError ? (
              <FeedSkeleton />
            ) : (
              <NewsFeed
                initialItems={items}
                view={view}
                folders={folders}
                total={feedTotal}
                page={page}
              />
            )}
          </div>
        </div>
      </main>
    </>
  );
}
