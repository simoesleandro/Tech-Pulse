"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { memo, useTransition } from "react";

import { HypeStars } from "@/components/HypeStars";
import { assignNewsFolder, patchBookmarkStatus, patchReadStatus } from "@/lib/api";
import { getSourceTheme } from "@/lib/sources";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsCardProps {
  item: NewsItem;
  view: FeedView;
  folders?: TopicFolder[];
  onUpdate: (item: NewsItem) => void;
  selected?: boolean;
  onToggleSelect?: (id: number) => void;
  onDelete?: (id: number) => void;
  selectionDisabled?: boolean;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function BookmarkIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M5 3.5h10v13l-5-3.25L5 16.5v-13z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M4.5 5.5h11M8 5.5V4.5h4v1M7 8.5v5M10 8.5v5M13 8.5v5M6 5.5l.6 9.5h6.8l.6-9.5" />
    </svg>
  );
}

function CardField({
  label,
  labelClass,
  children,
}: {
  label: string;
  labelClass: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2 border-t border-border/40 pt-2 first:border-t-0 first:pt-0">
      <span
        className={`font-mono text-[10px] uppercase tracking-wide ${labelClass}`}
      >
        {label}
      </span>
      <div className="min-w-0 text-sm text-foreground">{children}</div>
    </div>
  );
}

function NewsCardComponent({
  item,
  view,
  folders = [],
  onUpdate,
  selected = false,
  onToggleSelect,
  onDelete,
  selectionDisabled = false,
}: NewsCardProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const isUnread = !item.is_read;
  const theme = getSourceTheme(item.source);
  const busy = isPending || selectionDisabled;

  function handleRead() {
    startTransition(async () => {
      const updated = await patchReadStatus(item.id, !item.is_read);
      onUpdate(updated);
      router.refresh();
    });
  }

  function handleBookmark() {
    startTransition(async () => {
      const updated = await patchBookmarkStatus(item.id, !item.is_bookmarked);
      onUpdate(updated);
      router.refresh();
    });
  }

  function handleFolderChange(folderId: number | null) {
    startTransition(async () => {
      const updated = await assignNewsFolder(item.id, folderId);
      onUpdate(updated);
      router.refresh();
    });
  }

  return (
    <article
      className={`feed-item card-hover group relative rounded-lg border transition-all duration-200 ${theme.cardClass} ${
        isUnread ? "opacity-100" : "opacity-80"
      } ${selected ? "ring-2 ring-cyan/50 ring-offset-1 ring-offset-slate-dark" : ""}`}
    >
      {isUnread ? (
        <span
          aria-hidden="true"
          className="source-trace pulse-trace absolute bottom-3 left-0 top-3 w-1 rounded-full"
        />
      ) : null}

      <div className="flex flex-col gap-3 px-4 py-4 pl-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          {onToggleSelect ? (
            <label className="mt-1 flex cursor-pointer items-start">
              <input
                type="checkbox"
                checked={selected}
                disabled={busy}
                onChange={() => onToggleSelect(item.id)}
                className="mt-0.5 h-4 w-4 cursor-pointer accent-cyan"
                aria-label={`Selecionar ${item.title}`}
              />
            </label>
          ) : null}

          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`source-badge ${theme.badgeClass}`}>
                  {theme.label}
                </span>
                {item.folder_name ? (
                  <span className="rounded-full border border-cyan/30 bg-cyan/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-cyan">
                    {item.folder_name}
                  </span>
                ) : null}
              </div>
              <time
                dateTime={item.created_at}
                className="font-mono text-[10px] text-muted"
              >
                {formatTimestamp(item.created_at)}
              </time>
            </div>

            <CardField label="Fonte" labelClass={theme.fieldLabelClass}>
              <span className="font-mono text-xs uppercase tracking-wide">
                {theme.label}
              </span>
            </CardField>

            <CardField label="Título" labelClass={theme.fieldLabelClass}>
              <p className="font-medium leading-snug">{item.title}</p>
            </CardField>

            <CardField label="Descrição" labelClass={theme.fieldLabelClass}>
              <p className="leading-relaxed text-muted">
                {item.description || "Aguardando tradução e resumo pelo Gemma4."}
              </p>
            </CardField>

            <CardField label="Link" labelClass={theme.fieldLabelClass}>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`link-interactive break-all font-mono text-xs ${theme.linkClass}`}
              >
                {item.url}
              </a>
            </CardField>

            <CardField label="Hype" labelClass={theme.fieldLabelClass}>
              <div className="flex flex-col gap-1">
                <HypeStars score={item.hype_score} />
                <span className="text-xs text-muted">
                  Avaliado pelo Gemma4 com base no engajamento da comunidade.
                </span>
              </div>
            </CardField>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-end sm:pt-1">
          {view !== "read" ? (
            <button
              type="button"
              onClick={handleRead}
              disabled={busy}
              className="btn-interactive rounded border border-border/80 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted"
            >
              {isPending ? "…" : item.is_read ? "Marcar não lida" : "Marcar lida"}
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleBookmark}
            disabled={busy}
            aria-label={item.is_bookmarked ? "Remover dos salvos" : "Salvar artigo"}
            aria-pressed={item.is_bookmarked}
            className={`btn-interactive rounded border p-2 ${
              item.is_bookmarked
                ? "border-current bg-white/5 text-foreground"
                : "border-border/80 text-muted"
            }`}
          >
            <BookmarkIcon filled={item.is_bookmarked} />
          </button>

          {folders.length > 0 ? (
            <select
              disabled={busy}
              value={item.folder_id ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                handleFolderChange(value ? Number(value) : null);
              }}
              className="max-w-[140px] cursor-pointer rounded border border-border/80 bg-slate-dark px-2 py-1.5 font-mono text-[10px] text-muted"
              aria-label="Pasta do artigo"
            >
              <option value="">Sem pasta</option>
              {folders.map((folder) => (
                <option key={folder.id} value={folder.id}>
                  {folder.name}
                </option>
              ))}
            </select>
          ) : null}

          {onDelete ? (
            <button
              type="button"
              onClick={() => onDelete(item.id)}
              disabled={busy}
              aria-label="Excluir notícia"
              className="btn-interactive btn-danger rounded border border-crimson/40 p-2 text-crimson"
            >
              <TrashIcon />
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export const NewsCard = memo(NewsCardComponent);
