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
}: BulkActionBarProps) {
  if (selectedCount === 0) {
    return null;
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
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Lidas
        </button>
        <button
          type="button"
          onClick={onMarkUnread}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Não lidas
        </button>
        <button
          type="button"
          onClick={onBookmark}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Favoritar
        </button>
        <button
          type="button"
          onClick={onUnbookmark}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Desfavoritar
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
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Tirar pasta
        </button>

        {onExportObsidian ? (
          <button
            type="button"
            onClick={onExportObsidian}
            disabled={disabled}
            className="btn-interactive rounded-md border border-violet-400/40 bg-violet-500/10 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet-300"
          >
            Obsidian
          </button>
        ) : null}

        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="btn-interactive btn-danger rounded-md border border-crimson/50 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson"
        >
          Excluir
        </button>
      </div>
    </div>
  );
}
