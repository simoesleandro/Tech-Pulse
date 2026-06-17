"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { BulkActionBar } from "@/components/BulkActionBar";
import { EmptyState } from "@/components/EmptyState";
import { FeedPagination } from "@/components/FeedPagination";
import { NewsCard } from "@/components/NewsCard";
import { ObsidianExportModal } from "@/components/ObsidianExportModal";
import { NewsDetailDrawer } from "@/components/NewsDetailDrawer";
import {
  bulkDeleteNews,
  bulkUpdateNews,
} from "@/lib/api";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsFeedProps {
  initialItems: NewsItem[];
  view: FeedView;
  folders: TopicFolder[];
  total: number;
  page: number;
}

export function NewsFeed({ initialItems, view, folders, total, page }: NewsFeedProps) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [obsidianExportIds, setObsidianExportIds] = useState<number[] | null>(null);
  const [activeDetailItem, setActiveDetailItem] = useState<NewsItem | null>(null);

  const itemIdsKey = initialItems.map((item) => item.id).join(",");

  useEffect(() => {
    setItems(initialItems);
  }, [itemIdsKey, initialItems]);

  useEffect(() => {
    setSelectedIds([]);
    setActionMessage(null);
  }, [view, page, itemIdsKey]);

  const selectedCount = useMemo(
    () => items.filter((item) => selectedIds.includes(item.id)).length,
    [items, selectedIds],
  );

  const allSelected = items.length > 0 && selectedCount === items.length;

  function selectedItems(): NewsItem[] {
    return items.filter((item) => selectedIds.includes(item.id));
  }

  function handleUpdate(updated: NewsItem) {
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
    if (activeDetailItem?.id === updated.id) {
      setActiveDetailItem(updated);
    }
    router.refresh();
  }

  function handleRemove(id: number) {
    setItems((current) => current.filter((item) => item.id !== id));
    setSelectedIds((current) => current.filter((itemId) => itemId !== id));
    router.refresh();
  }

  function handleToggleSelect(id: number) {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((itemId) => itemId !== id)
        : [...current, id],
    );
  }

  async function runBulkAction(actionId: string, action: () => Promise<void>) {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    setBusyAction(actionId);
    setActionMessage(null);
    try {
      await action();
      router.refresh();
    } finally {
      setIsBusy(false);
      setBusyAction(null);
    }
  }

  function handleBulkDelete() {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    if (!window.confirm(`Excluir ${ids.length} notícia(s)?`)) {
      return;
    }
    void runBulkAction("delete", async () => {
      await bulkDeleteNews(ids);
      setItems((current) => current.filter((item) => !ids.includes(item.id)));
      setSelectedIds([]);
    });
  }

  function handleBulkRead(isRead: boolean) {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    void runBulkAction(isRead ? "read" : "unread", async () => {
      await bulkUpdateNews({ ids, is_read: isRead });
      setItems((current) =>
        current.map((item) =>
          ids.includes(item.id) ? { ...item, is_read: isRead } : item,
        ),
      );
    });
  }

  function handleBulkBookmark(isBookmarked: boolean) {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    void runBulkAction(isBookmarked ? "bookmark" : "unbookmark", async () => {
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
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    const folder = folders.find((entry) => entry.id === folderId);
    void runBulkAction(`folder-${folderId}`, async () => {
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
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    void runBulkAction("clear-folder", async () => {
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

  function handleBulkExportObsidian() {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    setObsidianExportIds(ids);
  }

  function handleObsidianExport(ids: number[]) {
    setObsidianExportIds(ids);
  }

  if (items.length === 0) {
    return <EmptyState view={view} />;
  }

  return (
    <div className="flex flex-col gap-3 pb-24">
      {actionMessage ? (
        <p className="font-mono text-[10px] text-violet-300">{actionMessage}</p>
      ) : null}

      <ul className="flex flex-col gap-2" role="list">
        {items.map((item) => (
          <li key={item.id}>
            <NewsCard
              item={item}
              view={view}
              folders={folders}
              onUpdate={handleUpdate}
              onRemove={handleRemove}
              onObsidianExport={handleObsidianExport}
              selected={selectedIds.includes(item.id)}
              onToggleSelect={handleToggleSelect}
              selectionDisabled={isBusy}
              onViewDetail={setActiveDetailItem}
            />
          </li>
        ))}
      </ul>

      <Suspense fallback={null}>
        <FeedPagination total={total} page={page} />
      </Suspense>

      <BulkActionBar
        selectedCount={selectedCount}
        totalCount={items.length}
        allSelected={allSelected}
        folders={folders}
        onSelectAll={() => setSelectedIds(items.map((item) => item.id))}
        onClearSelection={() => setSelectedIds([])}
        onMarkRead={() => handleBulkRead(true)}
        onMarkUnread={() => handleBulkRead(false)}
        onBookmark={() => handleBulkBookmark(true)}
        onUnbookmark={() => handleBulkBookmark(false)}
        onMoveToFolder={handleBulkMoveToFolder}
        onRemoveFromFolder={handleBulkRemoveFromFolder}
        onDelete={handleBulkDelete}
        onExportObsidian={handleBulkExportObsidian}
        disabled={isBusy}
        busyAction={busyAction}
      />

      <ObsidianExportModal
        ids={obsidianExportIds ?? []}
        open={Boolean(obsidianExportIds?.length)}
        onClose={() => setObsidianExportIds(null)}
        onComplete={(result) => {
          const exportedAt = new Date().toISOString();
          const exportedSet = new Set(result.exported_ids ?? []);
          setItems((current) =>
            current.map((item) =>
              exportedSet.has(item.id)
                ? { ...item, obsidian_exported_at: exportedAt }
                : item,
            ),
          );
          setActionMessage(`${result.exported} nota(s) formatada(s) e enviada(s) ao Obsidian.`);
          router.refresh();
        }}
      />

      <NewsDetailDrawer
        item={activeDetailItem}
        onClose={() => setActiveDetailItem(null)}
        onUpdate={handleUpdate}
        onObsidianExport={handleObsidianExport}
        folders={folders}
      />
    </div>
  );
}
