"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { NewsCard } from "@/components/NewsCard";
import type { FeedView, NewsItem } from "@/lib/types";

interface NewsFeedProps {
  initialItems: NewsItem[];
  view: FeedView;
}

export function NewsFeed({ initialItems, view }: NewsFeedProps) {
  const [items, setItems] = useState(initialItems);

  useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const visibleItems = useMemo(() => {
    if (view === "saved") {
      return items.filter((item) => item.is_bookmarked);
    }
    if (view === "read") {
      return items.filter((item) => item.is_read);
    }
    return items.filter((item) => !item.is_read);
  }, [items, view]);

  function handleUpdate(updated: NewsItem) {
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  if (visibleItems.length === 0) {
    return <EmptyState view={view} />;
  }

  return (
    <ul className="flex flex-col gap-2" role="list">
      {visibleItems.map((item) => (
        <li key={item.id}>
          <NewsCard item={item} view={view} onUpdate={handleUpdate} />
        </li>
      ))}
    </ul>
  );
}
