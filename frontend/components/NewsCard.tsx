"use client";

import { memo, useTransition } from "react";

import { patchBookmarkStatus, patchReadStatus } from "@/lib/api";
import type { FeedView, NewsItem } from "@/lib/types";

interface NewsCardProps {
  item: NewsItem;
  view: FeedView;
  onUpdate: (item: NewsItem) => void;
}

function formatSource(source: string): string {
  const labels: Record<string, string> = {
    "dev.to": "dev.to",
    reddit: "reddit",
    github_trends: "github",
  };
  return labels[source] ?? source;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function BookmarkIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M5 3.5h10v13l-5-3.25L5 16.5v-13z" />
    </svg>
  );
}

function NewsCardComponent({ item, view, onUpdate }: NewsCardProps) {
  const [isPending, startTransition] = useTransition();
  const isUnread = !item.is_read;

  function handleRead() {
    startTransition(async () => {
      const updated = await patchReadStatus(item.id, !item.is_read);
      onUpdate(updated);
    });
  }

  function handleBookmark() {
    startTransition(async () => {
      const updated = await patchBookmarkStatus(item.id, !item.is_bookmarked);
      onUpdate(updated);
    });
  }

  return (
    <article
      className={`feed-item group relative rounded-lg border bg-surface transition-colors hover:border-cyan/30 ${
        isUnread ? "border-border" : "border-border/70 opacity-80"
      }`}
    >
      {isUnread ? (
        <span
          aria-hidden="true"
          className="pulse-trace absolute bottom-3 left-0 top-3 w-0.5 rounded-full bg-cyan"
        />
      ) : null}

      <div className="flex flex-col gap-3 px-4 py-3 pl-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded border border-border bg-slate-dark px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
              {formatSource(item.source)}
            </span>
            <time
              dateTime={item.created_at}
              className="font-mono text-[10px] text-muted"
            >
              {formatTimestamp(item.created_at)}
            </time>
          </div>

          <h2 className="mt-2 text-sm font-medium leading-snug text-foreground sm:text-base">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-2 hover:text-cyan hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan"
            >
              {item.title}
            </a>
          </h2>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:pt-1">
          {view !== "read" ? (
            <button
              type="button"
              onClick={handleRead}
              disabled={isPending}
              className="rounded border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted transition-colors hover:border-cyan/40 hover:text-cyan focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:opacity-50"
            >
              {item.is_read ? "Não lida" : "Marcar lida"}
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleBookmark}
            disabled={isPending}
            aria-label={item.is_bookmarked ? "Remover dos salvos" : "Salvar artigo"}
            aria-pressed={item.is_bookmarked}
            className={`rounded border p-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:opacity-50 ${
              item.is_bookmarked
                ? "border-cyan bg-cyan/10 text-cyan"
                : "border-border text-muted hover:border-cyan/40 hover:text-cyan"
            }`}
          >
            <BookmarkIcon filled={item.is_bookmarked} />
          </button>
        </div>
      </div>
    </article>
  );
}

export const NewsCard = memo(NewsCardComponent);
