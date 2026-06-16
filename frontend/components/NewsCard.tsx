"use client";

import type { ReactNode } from "react";
import { memo, useTransition } from "react";

import { CardActionMenu } from "@/components/CardActionMenu";
import { HypeStars } from "@/components/HypeStars";
import { getSourceTheme } from "@/lib/sources";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";

interface NewsCardProps {
  item: NewsItem;
  view: FeedView;
  folders?: TopicFolder[];
  onUpdate: (item: NewsItem) => void;
  onRemove?: (id: number) => void;
  onObsidianExport?: (ids: number[]) => void;
  selected?: boolean;
  onToggleSelect?: (id: number) => void;
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
  onRemove,
  onObsidianExport,
  selected = false,
  onToggleSelect,
  selectionDisabled = false,
}: NewsCardProps) {
  const [isPending, startTransition] = useTransition();
  const isUnread = !item.is_read;
  const theme = getSourceTheme(item.source);
  const busy = isPending || selectionDisabled;

  function handleUpdate(updated: NewsItem) {
    startTransition(() => {
      onUpdate(updated);
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

      <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
        {onToggleSelect ? (
          <label className="flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={selected}
              disabled={busy}
              onChange={() => onToggleSelect(item.id)}
              className="h-4 w-4 cursor-pointer accent-cyan"
              aria-label={`Selecionar ${item.title}`}
            />
          </label>
        ) : null}
        <CardActionMenu
          item={item}
          view={view}
          folders={folders}
          onUpdate={handleUpdate}
          onRemove={onRemove}
          onObsidianExport={onObsidianExport}
          disabled={busy}
        />
      </div>

      <div className="flex flex-col gap-3 px-4 py-4 pl-5 pr-20">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 pr-8">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`source-badge ${theme.badgeClass}`}>
                {theme.label}
              </span>
              {item.is_bookmarked ? (
                <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-amber-200">
                  Salvo
                </span>
              ) : null}
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
              {item.ai_reasoning ? (
                <p className="text-xs italic leading-relaxed text-muted">
                  {item.ai_reasoning}
                </p>
              ) : (
                <span className="text-xs text-muted">
                  Avaliado pelo analista de hype com base no engajamento da comunidade.
                </span>
              )}
            </div>
          </CardField>
        </div>
      </div>
    </article>
  );
}

export const NewsCard = memo(NewsCardComponent);
