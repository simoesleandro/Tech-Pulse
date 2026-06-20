"use client";

import { useEffect, useRef, useState } from "react";

import type { FeedCountOptions } from "@/lib/api";
import { fetchPendingCount } from "@/lib/api";
import { useFeedNewArticles } from "@/hooks/useFeedNewArticles";

const PENDING_POLL_MS = 30_000;

function usePendingCount(): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let active = true;

    async function poll() {
      if (document.visibilityState !== "visible") return;
      try {
        const n = await fetchPendingCount();
        if (active) setCount(n);
      } catch {
        /* ignore */
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), PENDING_POLL_MS);
    const onVisibility = () => void poll();
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      active = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return count;
}

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
  const processingCount = usePendingCount();

  const showNew = pendingNew > 0;
  const showProcessing = processingCount > 0;

  if (!showNew && !showProcessing) {
    return null;
  }

  const newLabel =
    pendingNew === 1
      ? "1 novo artigo na fila"
      : `${pendingNew} novos artigos na fila`;

  const processingLabel =
    processingCount === 1
      ? "1 artigo sendo processado"
      : `${processingCount} artigos sendo processados`;

  return (
    <div className="flex flex-col gap-2">
      {showNew && (
        <div
          className="sticky top-2 z-30 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cyan/35 bg-cyan/10 px-4 py-2.5 shadow-[0_4px_24px_rgba(6,182,212,0.12)] backdrop-blur-sm"
          role="status"
          aria-live="polite"
        >
          <p className="font-mono text-xs text-cyan">{newLabel}</p>
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
      )}

      {showProcessing && (
        <div
          className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/8 px-4 py-2 font-mono text-[10px] text-amber-400"
          role="status"
          aria-live="polite"
        >
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
          {processingLabel}
        </div>
      )}
    </div>
  );
}
