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
  disabled = false,
}: BulkActionBarProps) {
  if (selectedCount === 0) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/80 bg-surface/60 px-3 py-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted">
          Selecione cards para ações em lote ({totalCount} visíveis)
        </p>
        <button
          type="button"
          onClick={onSelectAll}
          disabled={disabled || totalCount === 0}
          className="btn-interactive rounded-md border border-cyan/40 bg-cyan/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-cyan"
        >
          Selecionar todos
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-cyan/30 bg-cyan/5 px-3 py-3"
      role="toolbar"
      aria-label="Ações em lote"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-cyan">
          {selectedCount} selecionado{selectedCount === 1 ? "" : "s"}
          {allSelected ? " (todos)" : ""}
        </p>
        <div className="flex gap-2">
          {!allSelected ? (
            <button
              type="button"
              onClick={onSelectAll}
              disabled={disabled}
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
            >
              Selecionar todos
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClearSelection}
            disabled={disabled}
            className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
          >
            Limpar seleção
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onMarkRead}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Marcar lidas
        </button>
        <button
          type="button"
          onClick={onMarkUnread}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Marcar não lidas
        </button>
        <button
          type="button"
          onClick={onBookmark}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Favoritar
        </button>
        <button
          type="button"
          onClick={onUnbookmark}
          disabled={disabled}
          className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Remover favorito
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
            <option value="">Mover para pasta…</option>
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
          className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
        >
          Tirar da pasta
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="btn-interactive btn-danger rounded-md border border-crimson/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson"
        >
          Excluir
        </button>
      </div>
    </div>
  );
}
