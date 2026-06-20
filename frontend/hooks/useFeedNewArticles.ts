"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchFeedCount, type FeedCountOptions } from "@/lib/api";
import { dispatchFeedMutation } from "@/lib/feed-mutations";

const POLL_INTERVAL_MS = 90_000;

function buildFilterKey(options: FeedCountOptions): string {
  return JSON.stringify({
    view: options.view,
    folderId: options.folderId ?? null,
    source: options.source ?? null,
    hype: options.hype ?? null,
    min_hype: options.min_hype ?? null,
    obsidian_exported: options.obsidian_exported ?? null,
    q: options.q ?? null,
  });
}

export function useFeedNewArticles(
  initialTotal: number,
  options: FeedCountOptions,
  enabled: boolean,
) {
  const router = useRouter();
  const baselineRef = useRef(initialTotal);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const [pendingNew, setPendingNew] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const filterKey = useMemo(() => buildFilterKey(options), [
    options.view,
    options.folderId,
    options.source,
    options.hype,
    options.min_hype,
    options.obsidian_exported,
    options.q,
  ]);

  useEffect(() => {
    baselineRef.current = initialTotal;
    setPendingNew(0);
  }, [initialTotal, filterKey]);

  useEffect(() => {
    if (!enabled) {
      setPendingNew(0);
      return undefined;
    }

    async function poll() {
      if (document.visibilityState !== "visible") {
        return;
      }
      try {
        const count = await fetchFeedCount(optionsRef.current);
        if (count > baselineRef.current) {
          setPendingNew(count - baselineRef.current);
        }
      } catch {
        /* mantém banner anterior se houver */
      }
    }

    const timer = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
    const onVisibilityChange = () => void poll();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [enabled, filterKey]);

  const refresh = useCallback(() => {
    setIsRefreshing(true);
    setPendingNew(0);
    dispatchFeedMutation();
    router.refresh();
    window.setTimeout(() => setIsRefreshing(false), 800);
  }, [router]);

  const dismiss = useCallback(() => {
    setPendingNew(0);
    void fetchFeedCount(optionsRef.current)
      .then((count) => {
        baselineRef.current = count;
      })
      .catch(() => {
        baselineRef.current = initialTotal;
      });
  }, [initialTotal]);

  return { pendingNew, isRefreshing, refresh, dismiss };
}
