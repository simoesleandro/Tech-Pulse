"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { BulkActionBar } from "@/components/BulkActionBar";
import { EmptyState } from "@/components/EmptyState";
import { NewsCard } from "@/components/NewsCard";
import { bulkDeleteNews, bulkUpdateNews, deleteNewsItem } from "@/lib/api";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsFeedProps {
  initialItems: NewsItem[];
  view: FeedView;
  folders: TopicFolder[];
}

export function NewsFeed({ initialItems, view, folders }: NewsFeedProps) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBusy, setIsBusy] = useState(false);

  const itemIdsKey = initialItems.map((item) => item.id).join(",");

  useEffect(() => {
    setItems(initialItems);
  }, [itemIdsKey]);

  useEffect(() => {
    setSelectedIds([]);
  }, [view]);

  const visibleItems = useMemo(() => {
    if (view === "saved") {
      return items.filter((item) => item.is_bookmarked);
    }
    if (view === "read") {
      return items.filter((item) => item.is_read);
    }
    return items.filter((item) => !item.is_read);
  }, [items, view]);

  const selectedCount = useMemo(
    () => visibleItems.filter((item) => selectedIds.includes(item.id)).length,
    [visibleItems, selectedIds],
  );

  const allSelected =
    visibleItems.length > 0 && selectedCount === visibleItems.length;

  function handleUpdate(updated: NewsItem) {
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  function handleToggleSelect(id: number) {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((itemId) => itemId !== id)
        : [...current, id],
    );
  }

  function handleSelectAll() {
    setSelectedIds(visibleItems.map((item) => item.id));
  }

  function handleClearSelection() {
    setSelectedIds([]);
  }

  function removeFromState(ids: number[]) {
    const idSet = new Set(ids);
    setItems((current) => current.filter((item) => !idSet.has(item.id)));
    setSelectedIds((current) => current.filter((id) => !idSet.has(id)));
  }

  function selectedVisibleIds(): number[] {
    return visibleItems
      .filter((item) => selectedIds.includes(item.id))
      .map((item) => item.id);
  }

  async function runBulkAction(action: () => Promise<void>) {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    try {
      await action();
      router.refresh();
    } finally {
      setIsBusy(false);
    }
  }

  function handleDeleteOne(id: number) {
    if (!window.confirm("Excluir esta notícia do feed?")) {
      return;
    }

    void runBulkAction(async () => {
      await deleteNewsItem(id);
      removeFromState([id]);
    });
  }

  function handleBulkDelete() {
    const ids = selectedVisibleIds();
    if (ids.length === 0) {
      return;
    }
    if (!window.confirm(`Excluir ${ids.length} notícia(s) selecionada(s)?`)) {
      return;
    }

    void runBulkAction(async () => {
      await bulkDeleteNews(ids);
      removeFromState(ids);
    });
  }

  function handleBulkRead(isRead: boolean) {
    const ids = selectedVisibleIds();
    if (ids.length === 0) {
      return;
    }

    void runBulkAction(async () => {
      await bulkUpdateNews({ ids, is_read: isRead });
      setItems((current) =>
        current.map((item) =>
          ids.includes(item.id) ? { ...item, is_read: isRead } : item,
        ),
      );
    });
  }

  function handleBulkBookmark(isBookmarked: boolean) {
    const ids = selectedVisibleIds();
    if (ids.length === 0) {
      return;
    }

    void runBulkAction(async () => {
      await bulkUpdateNews({ ids, is_bookmarked: isBookmarked });
      setItems((current) =>
        current.map((item) =>
          ids.includes(item.id)
            ? {
                ...item,
                is_bookmarked: isBookmarked,
                folder_id: isBookmarked ? item.folder_id : null,
                folder_name: isBookmarked ? item.folder_name : null,
              }
            : item,
        ),
      );
    });
  }

  function handleBulkMoveToFolder(folderId: number) {
    const ids = selectedVisibleIds();
    if (ids.length === 0) {
      return;
    }

    const folder = folders.find((entry) => entry.id === folderId);

    void runBulkAction(async () => {
      await bulkUpdateNews({ ids, folder_id: folderId });
      setItems((current) =>
        current.map((item) =>
          ids.includes(item.id)
            ? {
                ...item,
                is_bookmarked: true,
                folder_id: folderId,
                folder_name: folder?.name ?? item.folder_name,
              }
            : item,
        ),
      );
    });
  }

  function handleBulkRemoveFromFolder() {
    const ids = selectedVisibleIds();
    if (ids.length === 0) {
      return;
    }

    void runBulkAction(async () => {
      await bulkUpdateNews({ ids, clear_folder: true });
      setItems((current) =>
        current.map((item) =>
          ids.includes(item.id)
            ? { ...item, folder_id: null, folder_name: null }
            : item,
        ),
      );
    });
  }

  if (visibleItems.length === 0) {
    return <EmptyState view={view} />;
  }

  return (
    <div className="flex flex-col gap-3">
      <BulkActionBar
        selectedCount={selectedCount}
        totalCount={visibleItems.length}
        allSelected={allSelected}
        folders={folders}
        onSelectAll={handleSelectAll}
        onClearSelection={handleClearSelection}
        onMarkRead={() => handleBulkRead(true)}
        onMarkUnread={() => handleBulkRead(false)}
        onBookmark={() => handleBulkBookmark(true)}
        onUnbookmark={() => handleBulkBookmark(false)}
        onMoveToFolder={handleBulkMoveToFolder}
        onRemoveFromFolder={handleBulkRemoveFromFolder}
        onDelete={handleBulkDelete}
        disabled={isBusy}
      />

      <ul className="flex flex-col gap-2" role="list">
        {visibleItems.map((item) => (
          <li key={item.id}>
            <NewsCard
              item={item}
              view={view}
              folders={folders}
              onUpdate={handleUpdate}
              selected={selectedIds.includes(item.id)}
              onToggleSelect={handleToggleSelect}
              onDelete={handleDeleteOne}
              selectionDisabled={isBusy}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
