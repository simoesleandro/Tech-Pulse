"use client";

import type { ReactNode } from "react";
import { memo, useTransition } from "react";

import { CardActionMenu } from "@/components/CardActionMenu";
import { HypeStars } from "@/components/HypeStars";
import { getSourceTheme } from "@/lib/sources";
import type { FeedView, NewsItem, TopicFolder } from "@/lib/types";
import { parseAiReasoning } from "@/lib/utils";

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
  onViewDetail?: (item: NewsItem) => void;
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
  onViewDetail,
}: NewsCardProps) {
  const [isPending, startTransition] = useTransition();
  const isUnread = !item.is_read;
  const theme = getSourceTheme(item.source);
  const busy = isPending || selectionDisabled;
  const parsedReasoning = parseAiReasoning(item.ai_reasoning);

  function handleUpdate(updated: NewsItem) {
    startTransition(() => {
      onUpdate(updated);
    });
  }

  const handleCardClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (
      target.closest("button") ||
      target.closest("a") ||
      target.closest("input") ||
      target.closest("label") ||
      target.classList.contains("cursor-pointer")
    ) {
      return;
    }
    if (onViewDetail) {
      onViewDetail(item);
    }
  };

  const hypeClass = {
    3: "card-hype-3",
    4: "card-hype-4",
    5: "card-hype-5",
  }[item.hype_score] || "";

  return (
    <article
      onClick={handleCardClick}
      className={`feed-item card-hover group relative rounded-lg border transition-all duration-200 ${theme.cardClass} ${hypeClass} ${
        isUnread ? "opacity-100" : "opacity-80"
      } ${selected ? "ring-2 ring-cyan/50 ring-offset-1 ring-offset-slate-dark" : ""} ${
        onViewDetail ? "cursor-pointer" : ""
      }`}
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
              {item.obsidian_exported_at ? (
                <span
                  className="rounded-full border border-violet-400/40 bg-violet-500/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-violet-300"
                  title={`Exportado ao Obsidian em ${formatTimestamp(item.obsidian_exported_at)}`}
                >
                  Obsidian
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
            <div>
              <p className={`font-medium leading-snug ${onViewDetail ? "group-hover:text-cyan transition-colors" : ""}`}>
                {item.title}
              </p>
              {parsedReasoning ? (
                <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 items-center font-mono text-[9px] text-muted">
                  <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-1 py-0.5 border border-border/20">
                    Novidade: <strong className="text-cyan">{parsedReasoning.novelty ?? "-"}</strong>
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-1 py-0.5 border border-border/20">
                    Utilidade: <strong className="text-cyan">{parsedReasoning.practicality ?? "-"}</strong>
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-1 py-0.5 border border-border/20">
                    Comunidade: <strong className="text-cyan">{parsedReasoning.communitySignal ?? "-"}</strong>
                  </span>
                  {parsedReasoning.explanation && (
                    <span
                      className="ml-1 cursor-help text-violet hover:text-violet-300 underline underline-offset-2"
                      title={parsedReasoning.explanation}
                    >
                      (Reasoning completo)
                    </span>
                  )}
                </div>
              ) : null}
            </div>
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

