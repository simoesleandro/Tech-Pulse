"use client";

import type { FeedCountOptions } from "@/lib/api";
import { useFeedNewArticles } from "@/hooks/useFeedNewArticles";

interface FeedNewArticlesBannerProps {
  initialTotal: number;
  query: FeedCountOptions;
  enabled?: boolean;
}

export function FeedNewArticlesBanner({
  initialTotal,
  query,
  enabled = true,
}: FeedNewArticlesBannerProps) {
  const { pendingNew, isRefreshing, refresh, dismiss } = useFeedNewArticles(
    initialTotal,
    query,
    enabled && query.view === "queue",
  );

  if (pendingNew <= 0) {
    return null;
  }

  const label =
    pendingNew === 1
      ? "1 novo artigo na fila"
      : `${pendingNew} novos artigos na fila`;

  return (
    <div
      className="sticky top-2 z-30 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cyan/35 bg-cyan/10 px-4 py-2.5 shadow-[0_4px_24px_rgba(6,182,212,0.12)] backdrop-blur-sm"
      role="status"
      aria-live="polite"
    >
      <p className="font-mono text-xs text-cyan">{label}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={dismiss}
          disabled={isRefreshing}
          className="btn-interactive rounded-md border border-border px-3 py-1 font-mono text-[10px] uppercase tracking-wide text-muted hover:text-foreground disabled:opacity-50"
        >
          Depois
        </button>
        <button
          type="button"
          onClick={refresh}
          disabled={isRefreshing}
          className="btn-interactive rounded-md border border-cyan bg-cyan/15 px-3 py-1 font-mono text-[10px] uppercase tracking-wide text-cyan disabled:opacity-50"
        >
          {isRefreshing ? "Atualizando…" : "Atualizar feed"}
        </button>
      </div>
    </div>
  );
}
