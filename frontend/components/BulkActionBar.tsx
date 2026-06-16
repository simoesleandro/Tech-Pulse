"use client";

interface BulkActionBarProps {
  selectedCount: number;
  totalCount: number;
  allSelected: boolean;
  folders: Array<{ id: number; name: string }>;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onMarkRead: () => void;
  onMarkUnread: () => void;
  onBookmark: () => void;
  onUnbookmark: () => void;
  onMoveToFolder: (folderId: number) => void;
  onRemoveFromFolder: () => void;
  onDelete: () => void;
  onExportObsidian?: () => void;
  disabled?: boolean;
  busyAction?: string | null;
}

export function BulkActionBar({
  selectedCount,
  totalCount,
  allSelected,
  folders,
  onSelectAll,
  onClearSelection,
  onMarkRead,
  onMarkUnread,
  onBookmark,
  onUnbookmark,
  onMoveToFolder,
  onRemoveFromFolder,
  onDelete,
  onExportObsidian,
  disabled = false,
  busyAction = null,
}: BulkActionBarProps) {
  if (selectedCount === 0) {
    return null;
  }

  function actionClass(actionId: string, extra = ""): string {
    const isLoading = busyAction === actionId;
    return `btn-interactive rounded-md border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide ${
      isLoading ? "border-cyan/50 text-cyan" : extra || "border-border text-muted"
    }`;
  }

  function ActionSpinner() {
    return (
      <span
        className="mr-1 inline-block h-3 w-3 animate-spin rounded-full border border-cyan/30 border-t-cyan"
        aria-hidden="true"
      />
    );
  }

  return (
    <div
      className="fixed bottom-4 left-1/2 z-40 w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 rounded-lg border border-cyan/40 bg-surface-elevated/95 px-4 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-md"
      role="toolbar"
      aria-label="Ações em lote"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-cyan">
          {selectedCount} selecionado{selectedCount === 1 ? "" : "s"}
          {allSelected ? ` · todos (${totalCount})` : ""}
        </p>
        <div className="flex gap-2">
          {!allSelected ? (
            <button
              type="button"
              onClick={onSelectAll}
              disabled={disabled}
              className="btn-interactive rounded-md border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-muted"
            >
              Todos
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClearSelection}
            disabled={disabled}
            className="btn-interactive rounded-md border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-muted"
          >
            Limpar
          </button>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onMarkRead}
          disabled={disabled || Boolean(busyAction)}
          className={actionClass("read")}
        >
          {busyAction === "read" ? <ActionSpinner /> : null}
          {busyAction === "read" ? "Marcando…" : "Lidas"}
        </button>
        <button
          type="button"
          onClick={onMarkUnread}
          disabled={disabled || Boolean(busyAction)}
          className={actionClass("unread")}
        >
          {busyAction === "unread" ? <ActionSpinner /> : null}
          {busyAction === "unread" ? "Marcando…" : "Não lidas"}
        </button>
        <button
          type="button"
          onClick={onBookmark}
          disabled={disabled || Boolean(busyAction)}
          className={actionClass("bookmark")}
        >
          {busyAction === "bookmark" ? <ActionSpinner /> : null}
          {busyAction === "bookmark" ? "Favoritando…" : "Favoritar"}
        </button>
        <button
          type="button"
          onClick={onUnbookmark}
          disabled={disabled || Boolean(busyAction)}
          className={actionClass("unbookmark")}
        >
          {busyAction === "unbookmark" ? <ActionSpinner /> : null}
          {busyAction === "unbookmark" ? "Removendo…" : "Desfavoritar"}
        </button>

        {folders.length > 0 ? (
          <select
            disabled={disabled}
            defaultValue=""
            onChange={(event) => {
              const value = event.target.value;
              if (value) {
                onMoveToFolder(Number(value));
                event.target.value = "";
              }
            }}
            className="cursor-pointer rounded-md border border-border bg-slate-dark px-2 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
            aria-label="Mover para pasta"
          >
            <option value="">Pasta…</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
        ) : null}

        <button
          type="button"
          onClick={onRemoveFromFolder}
          disabled={disabled || Boolean(busyAction)}
          className={actionClass("clear-folder")}
        >
          {busyAction === "clear-folder" ? <ActionSpinner /> : null}
          {busyAction === "clear-folder" ? "Removendo…" : "Tirar pasta"}
        </button>

        {onExportObsidian ? (
          <button
            type="button"
            onClick={onExportObsidian}
            disabled={disabled || Boolean(busyAction)}
            className={actionClass(
              "obsidian",
              "border-violet-400/40 bg-violet-500/10 text-violet-300",
            )}
          >
            {busyAction === "obsidian" ? <ActionSpinner /> : null}
            {busyAction === "obsidian" ? "Agente…" : "Obsidian"}
          </button>
        ) : null}

        <button
          type="button"
          onClick={onDelete}
          disabled={disabled || Boolean(busyAction)}
          className={`btn-interactive btn-danger rounded-md border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide ${
            busyAction === "delete"
              ? "border-crimson bg-crimson/20 text-crimson"
              : "border-crimson/50 text-crimson"
          }`}
        >
          {busyAction === "delete" ? <ActionSpinner /> : null}
          {busyAction === "delete" ? "Excluindo…" : "Excluir"}
        </button>
      </div>
    </div>
  );
}
