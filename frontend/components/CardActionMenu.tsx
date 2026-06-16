"use client";

import { useEffect, useRef, useState } from "react";

import {
  assignNewsFolder,
  deleteNewsItem,
  patchBookmarkStatus,
  patchReadStatus,
} from "@/lib/api";
import { copyObsidianMarkdown } from "@/lib/obsidian-export";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface CardActionMenuProps {
  item: NewsItem;
  view: FeedView;
  folders: TopicFolder[];
  onUpdate: (item: NewsItem) => void;
  onRemove?: (id: number) => void;
  onObsidianExport?: (ids: number[]) => void;
  disabled?: boolean;
}

function MenuIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
      <circle cx="10" cy="4" r="1.5" />
      <circle cx="10" cy="10" r="1.5" />
      <circle cx="10" cy="16" r="1.5" />
    </svg>
  );
}

function Spinner() {
  return (
    <span
      className="inline-block h-3 w-3 animate-spin rounded-full border border-current/30 border-t-current"
      aria-hidden="true"
    />
  );
}

export function CardActionMenu({
  item,
  view,
  folders,
  onUpdate,
  onRemove,
  onObsidianExport,
  disabled = false,
}: CardActionMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function runAction(actionId: string, action: () => Promise<void>, keepOpen = false) {
    if (activeActionId || disabled) {
      return;
    }
    setActiveActionId(actionId);
    setMessage(null);
    try {
      await action();
      if (!keepOpen) {
        setOpen(false);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Erro ao executar ação.");
    } finally {
      setActiveActionId(null);
    }
  }

  function menuButton(
    id: string,
    label: string,
    loadingLabel: string,
    onClick: () => Promise<void>,
    variant: "default" | "danger" = "default",
    confirm?: () => boolean,
    keepOpen = false,
  ) {
    const isLoading = activeActionId === id;

    return (
      <button
        key={id}
        type="button"
        disabled={Boolean(activeActionId) || disabled}
        onClick={() => {
          if (confirm && !confirm()) {
            return;
          }
          void runAction(id, onClick, keepOpen);
        }}
        className={`flex w-full items-center gap-2 px-3 py-2 text-left font-mono text-[10px] uppercase tracking-wide ${
          variant === "danger"
            ? "text-crimson hover:bg-crimson/10"
            : "text-foreground hover:bg-cyan/10 hover:text-cyan"
        } ${isLoading ? "opacity-100" : ""}`}
      >
        {isLoading ? <Spinner /> : null}
        <span>{isLoading ? loadingLabel : label}</span>
      </button>
    );
  }

  const menuItems = [
    view !== "read"
      ? menuButton(
          "toggle-read",
          item.is_read ? "Marcar não lida" : "Marcar lida",
          item.is_read ? "Marcando não lida…" : "Marcando lida…",
          async () => {
            const updated = await patchReadStatus(item.id, !item.is_read);
            onUpdate(updated);
          },
        )
      : null,
    menuButton(
      "toggle-bookmark",
      item.is_bookmarked ? "Remover favorito" : "Favoritar",
      item.is_bookmarked ? "Removendo favorito…" : "Favoritando…",
      async () => {
        const updated = await patchBookmarkStatus(item.id, !item.is_bookmarked);
        onUpdate(updated);
      },
    ),
  ];

  const folderItems =
    folders.length > 0
      ? [
          <div key="folder-divider" className="my-1 border-t border-border/60" />,
          <p
            key="folder-label"
            className="px-3 py-1 font-mono text-[9px] uppercase tracking-wide text-muted"
          >
            Mover para pasta
          </p>,
          ...folders.map((folder) =>
            menuButton(
              `folder-${folder.id}`,
              `→ ${folder.name}`,
              `Movendo para ${folder.name}…`,
              async () => {
                const updated = await assignNewsFolder(item.id, folder.id);
                onUpdate(updated);
              },
            ),
          ),
          item.folder_id
            ? menuButton("clear-folder", "Tirar da pasta", "Removendo da pasta…", async () => {
                const updated = await assignNewsFolder(item.id, null);
                onUpdate(updated);
              })
            : null,
        ]
      : [];

  const exportItems = [
    <div key="export-divider" className="my-1 border-t border-border/60" />,
    menuButton(
      "obsidian",
      "Enviar ao Obsidian",
      "Iniciando agente…",
      async () => {
        if (onObsidianExport) {
          onObsidianExport([item.id]);
          setOpen(false);
          return;
        }
        throw new Error("Exportação Obsidian indisponível.");
      },
      "default",
      undefined,
      true,
    ),
    menuButton("copy-md", "Copiar Markdown", "Formatando…", async () => {
      await copyObsidianMarkdown([item]);
      setMessage("Markdown formatado copiado.");
    }),
    <div key="delete-divider" className="my-1 border-t border-border/60" />,
    menuButton(
      "delete",
      "Excluir",
      "Excluindo…",
      async () => {
        await deleteNewsItem(item.id);
        onRemove?.(item.id);
      },
      "danger",
      () => window.confirm("Excluir esta notícia do feed?"),
    ),
  ];

  const menuBusy = Boolean(activeActionId);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled || menuBusy}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-busy={menuBusy}
        aria-label={`Ações para ${item.title}`}
        className="btn-interactive flex h-9 w-9 items-center justify-center rounded-md border border-border/80 bg-surface-elevated/90 text-muted shadow-sm backdrop-blur hover:border-cyan/50 hover:text-cyan"
      >
        {menuBusy ? <Spinner /> : <MenuIcon />}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-20 mt-1 min-w-[220px] overflow-hidden rounded-md border border-border bg-surface-elevated py-1 shadow-lg"
        >
          {[...menuItems, ...folderItems, ...exportItems].filter(Boolean)}
        </div>
      ) : null}

      {message ? (
        <p className="absolute right-0 top-full z-10 mt-1 max-w-[220px] rounded border border-violet-400/30 bg-surface px-2 py-1 font-mono text-[9px] text-violet-300">
          {message}
        </p>
      ) : null}
    </div>
  );
}
