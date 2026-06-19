"use client";

import { useEffect, useMemo, useState } from "react";

import type { NewsItem } from "@/lib/types";

export function useFeedSelection(items: NewsItem[], view: string, page: number) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  useEffect(() => {
    setSelectedIds([]);
  }, [view, page]);

  const selectedCount = useMemo(
    () => items.filter((item) => selectedIds.includes(item.id)).length,
    [items, selectedIds],
  );

  const allSelected = items.length > 0 && selectedCount === items.length;

  function selectedItems(): NewsItem[] {
    return items.filter((item) => selectedIds.includes(item.id));
  }

  function handleToggleSelect(id: number) {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((itemId) => itemId !== id)
        : [...current, id],
    );
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  function selectAll() {
    setSelectedIds(items.map((item) => item.id));
  }

  function removeFromSelection(id: number) {
    setSelectedIds((current) => current.filter((itemId) => itemId !== id));
  }

  return {
    selectedIds,
    setSelectedIds,
    selectedCount,
    allSelected,
    selectedItems,
    handleToggleSelect,
    clearSelection,
    selectAll,
    removeFromSelection,
  };
}
