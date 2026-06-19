"use client";

import { useState } from "react";

import type { ConfirmOptions } from "@/components/ConfirmDialog";
import { bulkDeleteNews, bulkUpdateNews } from "@/lib/api";
import {
  dispatchFeedMutation,
  shouldRemoveFromFeedView,
} from "@/lib/feed-mutations";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface UseFeedBulkActionsOptions {
  view: FeedView;
  folders: TopicFolder[];
  items: NewsItem[];
  setItems: React.Dispatch<React.SetStateAction<NewsItem[]>>;
  setFeedTotal: React.Dispatch<React.SetStateAction<number>>;
  selectedItems: () => NewsItem[];
  setSelectedIds: React.Dispatch<React.SetStateAction<number[]>>;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

export function useFeedBulkActions({
  view,
  folders,
  items,
  setItems,
  setFeedTotal,
  selectedItems,
  setSelectedIds,
  confirm,
}: UseFeedBulkActionsOptions) {
  const [isBusy, setIsBusy] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [obsidianExportIds, setObsidianExportIds] = useState<number[] | null>(null);
  const [exportMarkReadOnComplete, setExportMarkReadOnComplete] = useState(false);

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
      setActionMessage(
        "Erro na ação em lote: " + (err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setIsBusy(false);
      setBusyAction(null);
    }
  }

  async function handleBulkDelete() {
    const ids = selectedItems().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    const ok = await confirm({
      title: "Excluir notícias",
      message: `Excluir ${ids.length} notícia(s) selecionada(s)? Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (!ok) {
      return;
    }
    void runBulkAction("delete", async () => {
      const result = await bulkDeleteNews(ids);
      setItems((current) => current.filter((item) => !ids.includes(item.id)));
      setFeedTotal((current) => Math.max(0, current - ids.length));
      setSelectedIds([]);
      setActionMessage(`${result.affected} notícia(s) excluída(s).`);
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

  return {
    isBusy,
    busyAction,
    actionMessage,
    setActionMessage,
    obsidianExportIds,
    setObsidianExportIds,
    exportMarkReadOnComplete,
    setExportMarkReadOnComplete,
    handleBulkDelete,
    handleBulkRead,
    handleBulkBookmark,
    handleBulkMoveToFolder,
    handleBulkRemoveFromFolder,
    handleBulkExportObsidian,
    handleObsidianExportComplete,
    handleObsidianExport,
  };
}
