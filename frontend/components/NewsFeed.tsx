"use client";

import { Suspense, useEffect, useMemo, useState } from "react";

import { BulkActionBar } from "@/components/BulkActionBar";
import { EmptyState } from "@/components/EmptyState";
import { FeedPagination } from "@/components/FeedPagination";
import { NewsCard } from "@/components/NewsCard";
import { ObsidianExportModal } from "@/components/ObsidianExportModal";
import { NewsDetailDrawer } from "@/components/NewsDetailDrawer";
import { NewsTriageCard } from "@/components/NewsTriageCard";
import {
  bulkDeleteNews,
  bulkUpdateNews,
  patchReadStatus,
  assignNewsFolder,
} from "@/lib/api";
import {
  dispatchFeedMutation,
  shouldRemoveFromFeedView,
} from "@/lib/feed-mutations";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsFeedProps {
  initialItems: NewsItem[];
  view: FeedView;
  folders: TopicFolder[];
  total: number;
  page: number;
}

export function NewsFeed({ initialItems, view, folders, total, page }: NewsFeedProps) {
  const [items, setItems] = useState(initialItems);
  const [feedTotal, setFeedTotal] = useState(total);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [obsidianExportIds, setObsidianExportIds] = useState<number[] | null>(null);
  const [exportMarkReadOnComplete, setExportMarkReadOnComplete] = useState(false);
  const [activeDetailItem, setActiveDetailItem] = useState<NewsItem | null>(null);

  const [isTriageMode, setIsTriageMode] = useState(false);
  const [triageIndex, setTriageIndex] = useState(0);
  const [showFolders, setShowFolders] = useState(false);
  const [triageBusyAction, setTriageBusyAction] = useState<"archive" | "save" | "export" | null>(null);

  function handleTriageNext() {
    setTriageIndex((prev) => {
      if (prev >= items.length - 1) {
        setIsTriageMode(false);
        return 0;
      }
      return prev + 1;
    });
  }

  function handleTriagePrev() {
    setTriageIndex((prev) => Math.max(0, prev - 1));
  }

  async function handleTriageArchive(item: NewsItem) {
    if (triageBusyAction) return;
    const activeItem = item;
    setTriageBusyAction("archive");
    try {
      const updated = await patchReadStatus(activeItem.id, true);
      handleUpdate(updated);
      handleTriageNext();
    } catch (err) {
      setActionMessage("Erro ao arquivar: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setTriageBusyAction(null);
    }
  }

  async function handleTriageSaveToFolder(item: NewsItem, folderId: number) {
    if (triageBusyAction) return;
    const activeItem = item;
    setTriageBusyAction("save");
    try {
      const updated = await assignNewsFolder(activeItem.id, folderId === -1 ? null : folderId);
      handleUpdate(updated);
      handleTriageNext();
      setShowFolders(false);
    } catch (err) {
      setActionMessage("Erro ao salvar na pasta: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setTriageBusyAction(null);
    }
  }

  async function handleTriageExportObsidian(item: NewsItem) {
    if (triageBusyAction) return;
    const activeItem = item;
    setTriageBusyAction("export");
    try {
      setObsidianExportIds([activeItem.id]);
      const updated = await patchReadStatus(activeItem.id, true);
      handleUpdate(updated);
      handleTriageNext();
    } catch (err) {
      setActionMessage("Erro ao exportar/arquivar: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setTriageBusyAction(null);
    }
  }

  const itemIdsKey = initialItems.map((item) => item.id).join(",");

  useEffect(() => {
    if (!isTriageMode) {
      setItems(initialItems);
      setFeedTotal(total);
    }
  }, [itemIdsKey, initialItems, isTriageMode, total]);

  useEffect(() => {
    setSelectedIds([]);
    setActionMessage(null);
  }, [view, page]);

  useEffect(() => {
    setIsTriageMode(false);
    setTriageIndex(0);
    setShowFolders(false);
  }, [view]);

  useEffect(() => {
    if (!isTriageMode || items.length === 0) {
      return;
    }

    const activeItem = items[triageIndex];
    if (!activeItem) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (triageBusyAction) {
        return;
      }
      const activeEl = document.activeElement;
      if (
        activeEl &&
        (activeEl.tagName === "INPUT" ||
          activeEl.tagName === "TEXTAREA" ||
          activeEl.getAttribute("contenteditable") === "true")
      ) {
        return;
      }

      const key = e.key.toLowerCase();

      if (showFolders) {
        if (e.key === "Escape") {
          e.preventDefault();
          setShowFolders(false);
          return;
        }
        if (key === "s") {
          e.preventDefault();
          setShowFolders(false);
          return;
        }
        if (/^[1-9]$/.test(e.key)) {
          e.preventDefault();
          const folderIdx = parseInt(e.key, 10) - 1;
          const targetFolder = folders[folderIdx];
          if (targetFolder) {
            void handleTriageSaveToFolder(activeItem, targetFolder.id);
          }
          return;
        }
        if (e.key === "0") {
          e.preventDefault();
          void handleTriageSaveToFolder(activeItem, -1);
          return;
        }
      }

      if (e.key === "Escape") {
        e.preventDefault();
        setIsTriageMode(false);
        return;
      }

      if (key === "e") {
        e.preventDefault();
        void handleTriageArchive(activeItem);
      } else if (key === "s") {
        e.preventDefault();
        setShowFolders(true);
      } else if (key === "o") {
        e.preventDefault();
        void handleTriageExportObsidian(activeItem);
      } else if (key === "j" || e.key === "ArrowRight") {
        e.preventDefault();
        handleTriageNext();
      } else if (key === "k" || e.key === "ArrowLeft") {
        e.preventDefault();
        handleTriagePrev();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isTriageMode, triageIndex, items, showFolders, folders, triageBusyAction]);

  const selectedCount = useMemo(
    () => items.filter((item) => selectedIds.includes(item.id)).length,
    [items, selectedIds],
  );

  const allSelected = items.length > 0 && selectedCount === items.length;

  function selectedItems(): NewsItem[] {
    return items.filter((item) => selectedIds.includes(item.id));
  }

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
    setSelectedIds((current) => current.filter((itemId) => itemId !== id));
    setFeedTotal((current) => Math.max(0, current - 1));
    if (activeDetailItem?.id === id) {
      setActiveDetailItem(null);
    }
    dispatchFeedMutation();
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
      dispatchFeedMutation();
    } catch (err) {
      setActionMessage("Erro na ação em lote: " + (err instanceof Error ? err.message : String(err)));
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
      setFeedTotal((current) => Math.max(0, current - ids.length));
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
      setItems((current) => {
        const updated = current.map((item) =>
          ids.includes(item.id) ? { ...item, is_read: isRead } : item,
        );
        const next = updated.filter((item) => !shouldRemoveFromFeedView(item, view));
        const removed = updated.length - next.length;
        if (removed > 0) {
          setFeedTotal((totalCount) => Math.max(0, totalCount - removed));
        }
        return next;
      });
    });
  }

  function handleBulkBookmark(isBookmarked: boolean) {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    void runBulkAction(isBookmarked ? "bookmark" : "unbookmark", async () => {
      await bulkUpdateNews({ ids, is_bookmarked: isBookmarked });
      setItems((current) => {
        const updated = current.map((item) =>
          ids.includes(item.id)
            ? {
                ...item,
                is_bookmarked: isBookmarked,
                folder_id: isBookmarked ? item.folder_id : null,
                folder_name: isBookmarked ? item.folder_name : null,
              }
            : item,
        );
        const next = updated.filter((item) => !shouldRemoveFromFeedView(item, view));
        const removed = updated.length - next.length;
        if (removed > 0) {
          setFeedTotal((totalCount) => Math.max(0, totalCount - removed));
        }
        return next;
      });
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

  function handleBulkExportObsidian(markReadAfter = false) {
    const selected = selectedItems();
    const pending = selected.filter((item) => !item.obsidian_exported_at);
    if (pending.length === 0) {
      setActionMessage(
        selected.length > 0
          ? "Todos os itens selecionados já foram exportados ao Obsidian."
          : "Nenhum item selecionado.",
      );
      return;
    }
    const skipped = selected.length - pending.length;
    if (skipped > 0) {
      setActionMessage(
        `${skipped} já exportado(s) ignorado(s). Exportando ${pending.length} pendente(s).`,
      );
    }
    setExportMarkReadOnComplete(markReadAfter);
    setObsidianExportIds(pending.map((item) => item.id));
  }

  async function handleObsidianExportComplete(result: {
    exported: number;
    exported_ids: number[];
  }) {
    const exportedAt = new Date().toISOString();
    const exportedSet = new Set(result.exported_ids ?? []);
    let removedCount = 0;

    setItems((current) => {
      const next = current
        .map((item) => {
          if (!exportedSet.has(item.id)) {
            return item;
          }
          const updated = {
            ...item,
            obsidian_exported_at: exportedAt,
            is_read: exportMarkReadOnComplete ? true : item.is_read,
          };
          if (shouldRemoveFromFeedView(updated, view)) {
            removedCount += 1;
            return null;
          }
          return updated;
        })
        .filter((item): item is NewsItem => item !== null);
      return next;
    });

    if (removedCount > 0) {
      setFeedTotal((current) => Math.max(0, current - removedCount));
    }

    if (exportMarkReadOnComplete && result.exported_ids?.length) {
      try {
        await bulkUpdateNews({ ids: result.exported_ids, is_read: true });
      } catch {
        setActionMessage("Exportado, mas falha ao marcar como lido.");
      }
    }
    setActionMessage(
      exportMarkReadOnComplete
        ? `${result.exported} nota(s) exportada(s) e marcada(s) como lida(s).`
        : `${result.exported} nota(s) formatada(s) e enviada(s) ao Obsidian.`,
    );
    setExportMarkReadOnComplete(false);
    dispatchFeedMutation();
  }

  function handleObsidianExport(ids: number[]) {
    setObsidianExportIds(ids);
  }

  if (items.length === 0) {
    return <EmptyState view={view} />;
  }

  if (isTriageMode) {
    const activeIndex = Math.min(triageIndex, items.length - 1);
    const currentItem = items[activeIndex];

    return (
      <div className="flex flex-col gap-3 pb-24">
        {actionMessage ? (
          <p className="font-mono text-[10px] text-violet-300">{actionMessage}</p>
        ) : null}

        <NewsTriageCard
          item={currentItem}
          folders={folders}
          showFolders={showFolders}
          setShowFolders={setShowFolders}
          onArchive={handleTriageArchive}
          onSaveToFolder={handleTriageSaveToFolder}
          onExportObsidian={handleTriageExportObsidian}
          onNext={handleTriageNext}
          onPrev={handleTriagePrev}
          hasPrev={activeIndex > 0}
          hasNext={activeIndex < items.length - 1}
          progressText={`Item ${activeIndex + 1} de ${items.length}`}
          busyAction={triageBusyAction}
        />

        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={() => setIsTriageMode(false)}
            className="rounded-lg border border-border bg-surface px-4 py-2 font-mono text-xs uppercase tracking-wider text-muted hover:text-foreground transition-colors cursor-pointer"
          >
            Sair do Modo Triagem (Esc)
          </button>
        </div>

        <ObsidianExportModal
          ids={obsidianExportIds ?? []}
          open={Boolean(obsidianExportIds?.length)}
          onClose={() => {
            setObsidianExportIds(null);
            setExportMarkReadOnComplete(false);
          }}
          onComplete={(result) => {
            void handleObsidianExportComplete(result);
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-24">
      {actionMessage ? (
        <p className="font-mono text-[10px] text-violet-300">{actionMessage}</p>
      ) : null}

      {view === "queue" && items.length > 0 && (
        <div className="flex justify-end mb-2">
          <button
            type="button"
            onClick={() => {
              setIsTriageMode(true);
              setTriageIndex(0);
            }}
            className="flex items-center gap-2 rounded-xl border border-cyan/35 bg-cyan/5 px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-cyan hover:bg-cyan/15 transition-all shadow-md hover:shadow-cyan/5 cursor-pointer"
          >
            <svg className="h-4 w-4 animate-pulse text-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <span>Triar Fila Rápida</span>
          </button>
        </div>
      )}

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
        <FeedPagination total={feedTotal} page={page} />
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
        onExportObsidian={() => handleBulkExportObsidian(false)}
        onExportObsidianAndRead={() => handleBulkExportObsidian(true)}
        disabled={isBusy}
        busyAction={busyAction}
      />

      <ObsidianExportModal
        ids={obsidianExportIds ?? []}
        open={Boolean(obsidianExportIds?.length)}
        onClose={() => {
          setObsidianExportIds(null);
          setExportMarkReadOnComplete(false);
        }}
        onComplete={(result) => {
          void handleObsidianExportComplete(result);
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
