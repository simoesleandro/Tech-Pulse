"use client";

import { useState } from "react";
import { HypeStars } from "@/components/HypeStars";
import { getSourceTheme } from "@/lib/sources";
import type { NewsItem, TopicFolder } from "@/lib/types";
import { parseAiReasoning } from "@/lib/utils";

interface NewsTriageCardProps {
  item: NewsItem;
  folders: TopicFolder[];
  showFolders: boolean;
  setShowFolders: (show: boolean) => void;
  onArchive: (item: NewsItem) => void;
  onSaveToFolder: (item: NewsItem, folderId: number) => void;
  onExportObsidian: (item: NewsItem) => void;
  onNext: () => void;
  onPrev: () => void;
  hasPrev: boolean;
  hasNext: boolean;
  progressText: string;
  busyAction: "archive" | "save" | "export" | null;
}

function ButtonSpinner() {
  return (
    <span
      className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current/30 border-t-current"
      aria-hidden="true"
    />
  );
}

export function NewsTriageCard({
  item,
  folders,
  showFolders,
  setShowFolders,
  onArchive,
  onSaveToFolder,
  onExportObsidian,
  onNext,
  onPrev,
  hasPrev,
  hasNext,
  progressText,
  busyAction,
}: NewsTriageCardProps) {
  const theme = getSourceTheme(item.source);
  const parsedReasoning = parseAiReasoning(item.ai_reasoning);

  const isBusy = busyAction !== null;

  function handleArchiveClick() {
    if (isBusy) return;
    onArchive(item);
  }

  function handleObsidianClick() {
    if (isBusy) return;
    onExportObsidian(item);
  }

  function handleFolderSelect(folderId: number) {
    if (isBusy) return;
    onSaveToFolder(item, folderId);
  }

  const hypeClass = {
    3: "card-hype-3",
    4: "card-hype-4",
    5: "card-hype-5",
  }[item.hype_score] || "";

  return (
    <div className={`relative flex flex-col gap-6 rounded-2xl border border-border/60 bg-slate-900/70 p-6 shadow-2xl backdrop-blur-md transition-all duration-300 ${hypeClass}`}>
      {/* Top Bar / Progress & Navigation */}
      <div className="flex items-center justify-between border-b border-border/40 pb-4">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-bold tracking-wider text-cyan uppercase">
            Modo Triagem Rápida
          </span>
          <span className="rounded-full bg-surface/80 px-2.5 py-0.5 font-mono text-[10px] text-muted border border-border/40">
            {progressText}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPrev}
            disabled={!hasPrev || isBusy}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-surface/50 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-foreground hover:bg-cyan/10 hover:text-cyan disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-foreground transition-all cursor-pointer"
            title="Item anterior (Atalho: K ou Seta Esquerda)"
          >
            <kbd className="hidden sm:inline-block rounded bg-muted px-1.5 py-0.5 text-[9px] text-slate-800 font-bold">K</kbd>
            <span>Anterior</span>
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!hasNext || isBusy}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-surface/50 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-foreground hover:bg-cyan/10 hover:text-cyan disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-foreground transition-all cursor-pointer"
            title="Próximo item (Atalho: J ou Seta Direita)"
          >
            <span>Próximo</span>
            <kbd className="hidden sm:inline-block rounded bg-muted px-1.5 py-0.5 text-[9px] text-slate-800 font-bold">J</kbd>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-col gap-4">
        {/* Source and Metadata */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`source-badge ${theme.badgeClass}`}>
              {theme.label}
            </span>
            {item.folder_name && (
              <span className="rounded-full border border-cyan/30 bg-cyan/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-cyan">
                {item.folder_name}
              </span>
            )}
            {item.obsidian_exported_at && (
              <span className="rounded-full border border-violet-400/40 bg-violet-500/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-violet-300">
                Obsidian
              </span>
            )}
          </div>
          <time dateTime={item.created_at} className="font-mono text-xs text-muted">
            {new Date(item.created_at).toLocaleString("pt-BR", {
              day: "2-digit",
              month: "short",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
        </div>

        {/* Title */}
        <div className="space-y-2">
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground leading-snug">
            {item.title}
          </h2>
          {parsedReasoning && (
            <div className="flex flex-wrap gap-x-2 gap-y-1 items-center font-mono text-[10px] text-muted">
              <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-2 py-0.5 border border-border/20">
                Novidade: <strong className="text-cyan">{parsedReasoning.novelty ?? "-"}</strong>
              </span>
              <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-2 py-0.5 border border-border/20">
                Utilidade: <strong className="text-cyan">{parsedReasoning.practicality ?? "-"}</strong>
              </span>
              <span className="inline-flex items-center gap-1 rounded bg-surface/50 px-2 py-0.5 border border-border/20">
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
          )}
        </div>

        {/* Description / Summary */}
        <div className="rounded-xl border border-border/40 bg-surface/30 p-4 leading-relaxed text-muted-foreground text-sm sm:text-base">
          {item.description || "Aguardando tradução e resumo."}
        </div>

        {/* Link / URL */}
        <div className="flex flex-col gap-1.5 border-t border-border/40 pt-4">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">Link</span>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`link-interactive break-all font-mono text-xs hover:underline ${theme.linkClass}`}
          >
            {item.url}
          </a>
        </div>

        {/* Hype Assessment */}
        <div className="flex flex-col gap-2 rounded-xl border border-border/40 bg-surface/30 p-4">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">Hype / Impacto Técnico</span>
          <div className="flex flex-col gap-2">
            <HypeStars score={item.hype_score} />
            {item.ai_reasoning ? (
              <p className="text-xs sm:text-sm italic leading-relaxed text-muted">
                {item.ai_reasoning}
              </p>
            ) : (
              <span className="text-xs text-muted">
                Avaliado pelo analista de hype com base no engajamento da comunidade.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons Panel */}
      <div className="mt-4 border-t border-border/40 pt-6 flex flex-wrap items-center justify-center gap-4">
        {/* Archive Action */}
        <button
          type="button"
          onClick={handleArchiveClick}
          disabled={isBusy}
          className="flex flex-1 min-w-[140px] items-center justify-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-center font-mono text-xs uppercase tracking-wider text-red-400 hover:bg-red-500/15 disabled:opacity-50 disabled:hover:bg-red-500/5 transition-all cursor-pointer"
          title="Arquivar item como lido (Atalho: E)"
        >
          {busyAction === "archive" ? (
            <ButtonSpinner />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
          )}
          <span>{busyAction === "archive" ? "Arquivando…" : "Lixo / Lido"}</span>
          {busyAction !== "archive" && (
            <kbd className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-200">E</kbd>
          )}
        </button>

        {/* Save to Folder Action */}
        <div className="relative flex-1 min-w-[140px]">
          <button
            type="button"
            onClick={() => setShowFolders(!showFolders)}
            disabled={isBusy}
            className={`flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-3 text-center font-mono text-xs uppercase tracking-wider transition-all cursor-pointer ${
              showFolders
                ? "border-cyan/50 bg-cyan/15 text-cyan"
                : "border-cyan/20 bg-cyan/5 text-cyan-400 hover:bg-cyan/15"
            } disabled:opacity-50`}
            title="Escolher pasta para salvar (Atalho: S)"
          >
            {busyAction === "save" ? (
              <ButtonSpinner />
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            )}
            <span>{busyAction === "save" ? "Salvando…" : "Salvar Pasta"}</span>
            {busyAction !== "save" && (
              <kbd className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${showFolders ? "bg-cyan/30 text-cyan-200" : "bg-cyan/20 text-cyan-200"}`}>S</kbd>
            )}
          </button>

          {/* Inline Folder Selector Popover */}
          {showFolders && !isBusy && (
            <div className="absolute bottom-full left-0 right-0 z-50 mb-2 max-h-[280px] overflow-y-auto rounded-xl border border-border/80 bg-slate-950 p-2 shadow-2xl animate-in fade-in slide-in-from-bottom-2 duration-150">
              <div className="px-3 py-1.5 border-b border-border/40 flex items-center justify-between">
                <span className="font-mono text-[9px] uppercase tracking-wide text-muted font-bold">
                  Mover para:
                </span>
                <button
                  type="button"
                  onClick={() => setShowFolders(false)}
                  className="font-mono text-[9px] text-muted hover:text-foreground cursor-pointer"
                >
                  Fechar
                </button>
              </div>
              <div className="mt-1 space-y-1">
                {folders.length === 0 ? (
                  <p className="px-3 py-2 text-xs italic text-muted">Nenhuma pasta criada.</p>
                ) : (
                  folders.map((folder, index) => {
                    const numberKey = index + 1;
                    return (
                      <button
                        key={folder.id}
                        type="button"
                        onClick={() => handleFolderSelect(folder.id)}
                        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left font-mono text-[11px] text-foreground hover:bg-cyan/10 hover:text-cyan transition-colors cursor-pointer"
                      >
                        <span className="truncate">→ {folder.name}</span>
                        {numberKey <= 9 && (
                          <kbd className="rounded bg-surface px-1.5 py-0.5 text-[9px] text-slate-400 border border-border/40 font-bold">
                            {numberKey}
                          </kbd>
                        )}
                      </button>
                    );
                  })
                )}
                {item.folder_id && (
                  <button
                    type="button"
                    onClick={() => handleFolderSelect(-1)} // -1 to remove folder
                    className="flex w-full items-center justify-between rounded-lg border-t border-border/40 px-3 py-2 text-left font-mono text-[11px] text-crimson hover:bg-crimson/10 transition-colors cursor-pointer"
                  >
                    <span>Tirar da pasta</span>
                    <kbd className="rounded bg-crimson/10 px-1.5 py-0.5 text-[9px] text-crimson border border-crimson/20 font-bold">0</kbd>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Obsidian Export Action */}
        <button
          type="button"
          onClick={handleObsidianClick}
          disabled={isBusy}
          className="flex flex-1 min-w-[140px] items-center justify-center gap-2 rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-center font-mono text-xs uppercase tracking-wider text-violet-300 hover:bg-violet-500/15 disabled:opacity-50 disabled:hover:bg-violet-500/5 transition-all cursor-pointer"
          title="Exportar para Obsidian e arquivar (Atalho: O)"
        >
          {busyAction === "export" ? (
            <ButtonSpinner />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          )}
          <span>{busyAction === "export" ? "Exportando…" : "Obsidian"}</span>
          {busyAction !== "export" && (
            <kbd className="rounded bg-violet-500/20 px-1.5 py-0.5 text-[10px] font-bold text-violet-200">O</kbd>
          )}
        </button>
      </div>
    </div>
  );
}
