"use client";

import { useEffect, useState } from "react";

import { assignNewsFolder, patchReadStatus } from "@/lib/api";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface UseFeedTriageOptions {
  view: FeedView;
  items: NewsItem[];
  folders: TopicFolder[];
  isTriageMode: boolean;
  setIsTriageMode: (value: boolean) => void;
  onUpdate: (item: NewsItem) => void;
  onExportObsidian: (ids: number[]) => void;
  setActionMessage: (message: string | null) => void;
}

export function useFeedTriage({
  view,
  items,
  folders,
  isTriageMode,
  setIsTriageMode,
  onUpdate,
  onExportObsidian,
  setActionMessage,
}: UseFeedTriageOptions) {
  const [triageIndex, setTriageIndex] = useState(0);
  const [showFolders, setShowFolders] = useState(false);
  const [triageBusyAction, setTriageBusyAction] = useState<
    "archive" | "save" | "export" | null
  >(null);

  useEffect(() => {
    setIsTriageMode(false);
    setTriageIndex(0);
    setShowFolders(false);
  }, [view, setIsTriageMode]);

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
    setTriageBusyAction("archive");
    try {
      const updated = await patchReadStatus(item.id, true);
      onUpdate(updated);
      handleTriageNext();
    } catch (err) {
      setActionMessage(
        "Erro ao arquivar: " + (err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setTriageBusyAction(null);
    }
  }

  async function handleTriageSaveToFolder(item: NewsItem, folderId: number) {
    if (triageBusyAction) return;
    setTriageBusyAction("save");
    try {
      const updated = await assignNewsFolder(item.id, folderId === -1 ? null : folderId);
      onUpdate(updated);
      handleTriageNext();
      setShowFolders(false);
    } catch (err) {
      setActionMessage(
        "Erro ao salvar na pasta: " + (err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setTriageBusyAction(null);
    }
  }

  async function handleTriageExportObsidian(item: NewsItem) {
    if (triageBusyAction) return;
    setTriageBusyAction("export");
    try {
      onExportObsidian([item.id]);
      const updated = await patchReadStatus(item.id, true);
      onUpdate(updated);
      handleTriageNext();
    } catch (err) {
      setActionMessage(
        "Erro ao exportar/arquivar: " + (err instanceof Error ? err.message : String(err)),
      );
    } finally {
      setTriageBusyAction(null);
    }
  }

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
  }, [
    isTriageMode,
    triageIndex,
    items,
    showFolders,
    folders,
    triageBusyAction,
    setIsTriageMode,
  ]);

  function startTriage() {
    setIsTriageMode(true);
    setTriageIndex(0);
  }

  return {
    triageIndex,
    showFolders,
    setShowFolders,
    triageBusyAction,
    handleTriageNext,
    handleTriagePrev,
    handleTriageArchive,
    handleTriageSaveToFolder,
    handleTriageExportObsidian,
    startTriage,
  };
}
