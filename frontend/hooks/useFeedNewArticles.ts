"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchFeedCount, type FeedCountOptions } from "@/lib/api";
import { dispatchFeedMutation } from "@/lib/feed-mutations";

const POLL_INTERVAL_MS = 90_000;

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

  const filterKey = JSON.stringify(options);

  useEffect(() => {
    baselineRef.current = initialTotal;
    setPendingNew(0);
  }, [initialTotal, filterKey]);

  useEffect(() => {
    if (!enabled) {
      setPendingNew(0);
      return;
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

    const timer = setInterval(() => void poll(), POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", poll);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
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
    void fetchFeedCount(options)
      .then((count) => {
        baselineRef.current = count;
      })
      .catch(() => {
        baselineRef.current = initialTotal;
      });
  }, [initialTotal, options]);

  return { pendingNew, isRefreshing, refresh, dismiss };
}
