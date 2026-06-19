"use client";

import { Suspense, useEffect, useState } from "react";

import { BulkActionBar } from "@/components/BulkActionBar";
import { EmptyState } from "@/components/EmptyState";
import { FeedPagination } from "@/components/FeedPagination";
import { NewsCard } from "@/components/NewsCard";
import { ObsidianExportModal } from "@/components/ObsidianExportModal";
import { NewsDetailDrawer } from "@/components/NewsDetailDrawer";
import { NewsTriageCard } from "@/components/NewsTriageCard";
import { useConfirm } from "@/hooks/useConfirm";
import { useFeedBulkActions } from "@/hooks/useFeedBulkActions";
import { useFeedItems } from "@/hooks/useFeedItems";
import { useFeedSelection } from "@/hooks/useFeedSelection";
import { useFeedTriage } from "@/hooks/useFeedTriage";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsFeedProps {
  initialItems: NewsItem[];
  view: FeedView;
  folders: TopicFolder[];
  total: number;
  page: number;
  hasActiveFilters?: boolean;
}

export function NewsFeed({
  initialItems,
  view,
  folders,
  total,
  page,
  hasActiveFilters = false,
}: NewsFeedProps) {
  const { confirm, dialog } = useConfirm();
  const [isTriageMode, setIsTriageMode] = useState(false);

  const feed = useFeedItems(initialItems, total, view, isTriageMode);
  const selection = useFeedSelection(feed.items, view, page);
  const bulk = useFeedBulkActions({
    view,
    folders,
    items: feed.items,
    setItems: feed.setItems,
    setFeedTotal: feed.setFeedTotal,
    selectedItems: selection.selectedItems,
    setSelectedIds: selection.setSelectedIds,
    confirm,
  });

  const triage = useFeedTriage({
    view,
    items: feed.items,
    folders,
    isTriageMode,
    setIsTriageMode,
    onUpdate: feed.handleUpdate,
    onExportObsidian: bulk.handleObsidianExport,
    setActionMessage: bulk.setActionMessage,
  });

  useEffect(() => {
    bulk.setActionMessage(null);
  }, [view, page]);

  function handleRemove(id: number) {
    feed.handleRemove(id);
    selection.removeFromSelection(id);
  }

  if (feed.items.length === 0) {
    return (
      <>
        <EmptyState view={view} hasActiveFilters={hasActiveFilters} />
        {dialog}
      </>
    );
  }

  if (isTriageMode) {
    const activeIndex = Math.min(triage.triageIndex, feed.items.length - 1);
    const currentItem = feed.items[activeIndex];

    return (
      <div className="flex flex-col gap-3 pb-24">
        {bulk.actionMessage && !bulk.actionMessage.startsWith("Erro") ? (
          <p className="font-mono text-[10px] text-emerald">{bulk.actionMessage}</p>
        ) : null}

        <NewsTriageCard
          item={currentItem}
          folders={folders}
          showFolders={triage.showFolders}
          setShowFolders={triage.setShowFolders}
          onArchive={triage.handleTriageArchive}
          onSaveToFolder={triage.handleTriageSaveToFolder}
          onExportObsidian={triage.handleTriageExportObsidian}
          onNext={triage.handleTriageNext}
          onPrev={triage.handleTriagePrev}
          hasPrev={activeIndex > 0}
          hasNext={activeIndex < feed.items.length - 1}
          progressText={`Item ${activeIndex + 1} de ${feed.items.length}`}
          busyAction={triage.triageBusyAction}
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
          ids={bulk.obsidianExportIds ?? []}
          open={Boolean(bulk.obsidianExportIds?.length)}
          onClose={() => {
            bulk.setObsidianExportIds(null);
            bulk.setExportMarkReadOnComplete(false);
          }}
          onComplete={(result) => {
            void bulk.handleObsidianExportComplete(result);
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-24">
      {bulk.actionMessage && !bulk.actionMessage.startsWith("Erro") ? (
        <p className="font-mono text-[10px] text-emerald">{bulk.actionMessage}</p>
      ) : null}

      {view === "queue" && feed.items.length > 0 && (
        <div className="flex justify-end mb-2">
          <button
            type="button"
            onClick={triage.startTriage}
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
        {feed.items.map((item) => (
          <li key={item.id}>
            <NewsCard
              item={item}
              view={view}
              folders={folders}
              onUpdate={feed.handleUpdate}
              onRemove={handleRemove}
              onObsidianExport={bulk.handleObsidianExport}
              selected={selection.selectedIds.includes(item.id)}
              onToggleSelect={selection.handleToggleSelect}
              selectionDisabled={bulk.isBusy}
              onViewDetail={feed.setActiveDetailItem}
            />
          </li>
        ))}
      </ul>

      <Suspense fallback={null}>
        <FeedPagination total={feed.feedTotal} page={page} />
      </Suspense>

      <BulkActionBar
        selectedCount={selection.selectedCount}
        totalCount={feed.items.length}
        allSelected={selection.allSelected}
        folders={folders}
        onSelectAll={selection.selectAll}
        onClearSelection={selection.clearSelection}
        onMarkRead={() => bulk.handleBulkRead(true)}
        onMarkUnread={() => bulk.handleBulkRead(false)}
        onBookmark={() => bulk.handleBulkBookmark(true)}
        onUnbookmark={() => bulk.handleBulkBookmark(false)}
        onMoveToFolder={bulk.handleBulkMoveToFolder}
        onRemoveFromFolder={bulk.handleBulkRemoveFromFolder}
        onDelete={() => void bulk.handleBulkDelete()}
        onExportObsidian={() => bulk.handleBulkExportObsidian(false)}
        onExportObsidianAndRead={() => bulk.handleBulkExportObsidian(true)}
        disabled={bulk.isBusy}
        busyAction={bulk.busyAction}
        errorMessage={
          bulk.actionMessage?.startsWith("Erro") ? bulk.actionMessage : null
        }
      />

      <ObsidianExportModal
        ids={bulk.obsidianExportIds ?? []}
        open={Boolean(bulk.obsidianExportIds?.length)}
        onClose={() => {
          bulk.setObsidianExportIds(null);
          bulk.setExportMarkReadOnComplete(false);
        }}
        onComplete={(result) => {
          void bulk.handleObsidianExportComplete(result);
        }}
      />

      <NewsDetailDrawer
        item={feed.activeDetailItem}
        onClose={() => feed.setActiveDetailItem(null)}
        onUpdate={feed.handleUpdate}
        onObsidianExport={bulk.handleObsidianExport}
        folders={folders}
      />
      {dialog}
    </div>
  );
}
