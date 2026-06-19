"use client";

import { useEffect, useState } from "react";

import {
  dispatchFeedMutation,
  shouldRemoveFromFeedView,
} from "@/lib/feed-mutations";
import type { FeedView, NewsItem } from "@/lib/types";

export function useFeedItems(
  initialItems: NewsItem[],
  total: number,
  view: FeedView,
  isTriageMode: boolean,
) {
  const [items, setItems] = useState(initialItems);
  const [feedTotal, setFeedTotal] = useState(total);
  const [activeDetailItem, setActiveDetailItem] = useState<NewsItem | null>(null);

  const itemIdsKey = initialItems.map((item) => item.id).join(",");

  useEffect(() => {
    if (!isTriageMode) {
      setItems(initialItems);
      setFeedTotal(total);
    }
  }, [itemIdsKey, initialItems, isTriageMode, total]);

  function handleUpdate(updated: NewsItem) {
    let removed = false;
    setItems((current) => {
      if (shouldRemoveFromFeedView(updated, view)) {
        removed = true;
        return current.filter((item) => item.id !== updated.id);
      }
      return current.map((item) => (item.id === updated.id ? updated : item));
    });
    if (removed) {
      setFeedTotal((current) => Math.max(0, current - 1));
    }
    if (activeDetailItem?.id === updated.id) {
      setActiveDetailItem(
        shouldRemoveFromFeedView(updated, view) ? null : updated,
      );
    }
    dispatchFeedMutation();
  }

  function handleRemove(id: number) {
    setItems((current) => current.filter((item) => item.id !== id));
    setFeedTotal((current) => Math.max(0, current - 1));
    if (activeDetailItem?.id === id) {
      setActiveDetailItem(null);
    }
    dispatchFeedMutation();
  }

  return {
    items,
    setItems,
    feedTotal,
    setFeedTotal,
    activeDetailItem,
    setActiveDetailItem,
    handleUpdate,
    handleRemove,
  };
}
