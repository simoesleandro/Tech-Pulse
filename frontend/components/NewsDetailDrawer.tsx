"use client";

import { useEffect, useState, useTransition } from "react";
import type { NewsItem, TopicFolder } from "@/lib/types";
import { getSourceTheme } from "@/lib/sources";
import { parseAiReasoning } from "@/lib/utils";
import { HypeStars } from "@/components/HypeStars";
import {
  patchReadStatus,
  patchBookmarkStatus,
  assignNewsFolder,
  formatNewsForObsidian,
  exportNewsToObsidian,
} from "@/lib/api";

interface NewsDetailDrawerProps {
  item: NewsItem | null;
  onClose: () => void;
  onUpdate: (updated: NewsItem) => void;
  onObsidianExport?: (ids: number[]) => void;
  folders: TopicFolder[];
}

function MetricBar({ label, value }: { label: string; value?: number }) {
  if (value === undefined) return null;
  // value is between 0 and 5
  const pct = (value / 5) * 100;
  return (
    <div className="space-y-1">
      <div className="flex justify-between font-mono text-[10px] uppercase tracking-wider text-muted">
        <span>{label}</span>
        <span className="font-semibold text-cyan">{value}/5</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-dark overflow-hidden border border-border/20">
        <div
          className="h-full bg-cyan transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function NewsDetailDrawer({
  item,
  onClose,
  onUpdate,
  onObsidianExport,
  folders,
}: NewsDetailDrawerProps) {
  const [isPending, startTransition] = useTransition();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loadingMarkdown, setLoadingMarkdown] = useState(false);
  const [markdownError, setMarkdownError] = useState<string | null>(null);
  const [exportingInline, setExportingInline] = useState(false);
  const [exportInlineResult, setExportInlineResult] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  // Close on Escape key
  useEffect(() => {
    if (!item) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [item, onClose]);

  // Reset states when item changes
  useEffect(() => {
    setMarkdown(null);
    setMarkdownError(null);
    setExportInlineResult(null);
    setCopied(false);
    setPreviewOpen(false);
  }, [item?.id]);

  if (!item) return null;

  const activeItem = item;
  const theme = getSourceTheme(activeItem.source);
  const parsed = parseAiReasoning(activeItem.ai_reasoning);

  async function handleToggleRead() {
    startTransition(async () => {
      try {
        const updated = await patchReadStatus(activeItem.id, !activeItem.is_read);
        onUpdate(updated);
      } catch (err) {
        console.error("Falha ao atualizar status de leitura", err);
      }
    });
  }

  async function handleToggleBookmark() {
    startTransition(async () => {
      try {
        const updated = await patchBookmarkStatus(activeItem.id, !activeItem.is_bookmarked);
        onUpdate(updated);
      } catch (err) {
        console.error("Falha ao favoritar item", err);
      }
    });
  }

  async function handleFolderChange(folderIdStr: string) {
    const folderId = folderIdStr === "" ? null : Number(folderIdStr);
    startTransition(async () => {
      try {
        const updated = await assignNewsFolder(activeItem.id, folderId);
        onUpdate(updated);
      } catch (err) {
        console.error("Falha ao associar pasta", err);
      }
    });
  }

  async function handleLoadMarkdownPreview() {
    if (markdown || loadingMarkdown) return;
    setLoadingMarkdown(true);
    setMarkdownError(null);
    try {
      const res = await formatNewsForObsidian([activeItem.id]);
      setMarkdown(res.markdown);
    } catch (err) {
      setMarkdownError("Erro ao formatar nota para Obsidian.");
      console.error(err);
    } finally {
      setLoadingMarkdown(false);
    }
  }

  async function handleCopyMarkdown() {
    if (!markdown) return;
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Erro ao copiar markdown", err);
    }
  }

  async function handleExportInline() {
    setExportingInline(true);
    setExportInlineResult(null);
    try {
      const res = await exportNewsToObsidian([activeItem.id]);
      setExportInlineResult(`✓ Gravado no vault: ${res.paths[0] || "1 nota"}`);
      // Mark as exported locally
      const updated = { ...activeItem, obsidian_exported_at: new Date().toISOString() };
      onUpdate(updated);
    } catch (err) {
      setExportInlineResult(err instanceof Error ? `Erro: ${err.message}` : "Erro na exportação.");
    } finally {
      setExportingInline(false);
    }
  }

  function handleTriggerGlobalExport() {
    if (onObsidianExport) {
      onObsidianExport([activeItem.id]);
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300 pointer-events-auto"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[540px] bg-slate-dark border-l border-border flex flex-col shadow-2xl overflow-hidden animate-slide-in"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/80 px-6 py-4 bg-surface-elevated">
          <div className="flex items-center gap-2">
            <span className={`source-badge ${theme.badgeClass}`}>{theme.label}</span>
            {item.obsidian_exported_at && (
              <span className="rounded-full border border-violet-400/40 bg-violet-500/15 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-violet-300">
                ✓ Obsidian
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn-interactive rounded-md border border-border p-1.5 text-muted hover:text-foreground font-mono text-[10px] uppercase"
          >
            Fechar (Esc)
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* Main Titles */}
          <div className="space-y-2">
            <h2 id="drawer-title" className="text-xl font-bold leading-snug text-foreground">
              {item.title}
            </h2>
            {item.title_original && item.title_original !== item.title && (
              <p className="text-xs font-mono text-muted">
                Original: <span className="italic">{item.title_original}</span>
              </p>
            )}
            <div className="flex items-center gap-3 pt-1">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`link-interactive break-all font-mono text-xs ${theme.linkClass}`}
              >
                Visitar Link Original ↗
              </a>
            </div>
          </div>

          {/* Core Status & Actions Toolbar */}
          <div className="rounded-lg border border-border bg-surface-elevated p-4 space-y-4">
            <h3 className="font-mono text-[10px] uppercase tracking-wide text-muted border-b border-border/40 pb-1.5">
              Controles rápidos
            </h3>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={isPending}
                onClick={handleToggleRead}
                className={`btn-interactive rounded-md border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-xs ${
                  item.is_read
                    ? "border-border text-muted"
                    : "border-cyan/40 bg-cyan/10 text-cyan"
                }`}
              >
                {item.is_read ? "Marcar não lido" : "Lido"}
              </button>

              <button
                type="button"
                disabled={isPending}
                onClick={handleToggleBookmark}
                className={`btn-interactive rounded-md border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-xs ${
                  item.is_bookmarked
                    ? "border-amber-400/50 bg-amber-400/10 text-amber-200"
                    : "border-border text-muted hover:border-amber-400/40 hover:text-amber-200"
                }`}
              >
                {item.is_bookmarked ? "Salvo" : "Salvar no Feed"}
              </button>

              <button
                type="button"
                onClick={handleTriggerGlobalExport}
                className="btn-interactive rounded-md border border-violet/40 bg-violet/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet hover:border-violet"
              >
                Exportar (SSE)
              </button>
            </div>

            {/* Folder association inside the drawer */}
            <div className="flex flex-col gap-1.5 pt-2 border-t border-border/20">
              <label htmlFor="drawer-folder-select" className="font-mono text-[10px] uppercase tracking-wide text-muted">
                Associar Pasta
              </label>
              <select
                id="drawer-folder-select"
                disabled={isPending}
                value={item.folder_id ?? ""}
                onChange={(e) => void handleFolderChange(e.target.value)}
                className="rounded-md border border-border bg-slate-dark px-3 py-2 font-mono text-xs text-foreground focus:border-cyan/50 focus:outline-none"
              >
                <option value="">(Nenhuma pasta)</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Translation/Summary */}
          <div className="space-y-2">
            <h3 className="font-mono text-[10px] uppercase tracking-wide text-muted">
              Resumo & Tradução (Gemma)
            </h3>
            <p className="leading-relaxed text-sm text-foreground bg-surface/40 rounded-lg p-3 border border-border/60">
              {item.description || "Nenhum resumo disponível."}
            </p>
          </div>

          {/* IA Reasoning & Dimensions */}
          <div className="space-y-4">
            <div className="flex justify-between items-center border-b border-border/60 pb-1.5">
              <h3 className="font-mono text-[10px] uppercase tracking-wide text-muted">
                Análise de Hype & IA
              </h3>
              <HypeStars score={item.hype_score} />
            </div>

            {parsed ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <MetricBar label="Novidade" value={parsed.novelty} />
                <MetricBar label="Utilidade" value={parsed.practicality} />
                <MetricBar label="Comunidade" value={parsed.communitySignal} />
              </div>
            ) : null}

            {parsed?.explanation ? (
              <div className="bg-violet/5 rounded-lg border border-violet/20 p-3 space-y-1">
                <p className="font-mono text-[9px] uppercase tracking-wide text-violet-300">
                  Justificativa do Hype
                </p>
                <p className="text-xs leading-relaxed italic text-muted">
                  "{parsed.explanation}"
                </p>
              </div>
            ) : item.ai_reasoning ? (
              <div className="bg-violet/5 rounded-lg border border-violet/20 p-3">
                <p className="text-xs leading-relaxed italic text-muted">
                  "{item.ai_reasoning}"
                </p>
              </div>
            ) : null}
          </div>

          {/* Raw Engagement Metrics */}
          <div className="space-y-2">
            <h3 className="font-mono text-[10px] uppercase tracking-wide text-muted">
              Sinais Brutos de Engajamento
            </h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-md border border-border/60 bg-surface/30 px-3 py-2 text-center">
                <p className="font-mono text-[9px] uppercase text-muted">Reações</p>
                <p className="mt-0.5 font-mono text-base font-semibold text-foreground">
                  👍 {item.engagement_reactions}
                </p>
              </div>
              <div className="rounded-md border border-border/60 bg-surface/30 px-3 py-2 text-center">
                <p className="font-mono text-[9px] uppercase text-muted">Comentários</p>
                <p className="mt-0.5 font-mono text-base font-semibold text-foreground">
                  💬 {item.engagement_comments}
                </p>
              </div>
              <div className="rounded-md border border-border/60 bg-surface/30 px-3 py-2 text-center">
                <p className="font-mono text-[9px] uppercase text-muted">Stars (GH)</p>
                <p className="mt-0.5 font-mono text-base font-semibold text-foreground">
                  ⭐ {item.engagement_stars}
                </p>
              </div>
              <div className="rounded-md border border-border/60 bg-surface/30 px-3 py-2 text-center">
                <p className="font-mono text-[9px] uppercase text-muted">Upvotes</p>
                <p className="mt-0.5 font-mono text-base font-semibold text-foreground">
                  🔺 {item.engagement_ups}
                </p>
              </div>
            </div>
          </div>

          {/* Markdown Preview Section */}
          <div className="border border-border rounded-lg overflow-hidden bg-surface/40">
            <button
              type="button"
              onClick={() => {
                const open = !previewOpen;
                setPreviewOpen(open);
                if (open) {
                  void handleLoadMarkdownPreview();
                }
              }}
              className="flex w-full items-center justify-between px-4 py-3 bg-surface hover:bg-surface-elevated text-left transition-colors"
            >
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
                Preview do Markdown (Obsidian)
              </span>
              <span className="font-mono text-xs text-muted">
                {previewOpen ? "▲" : "▼"}
              </span>
            </button>

            {previewOpen && (
              <div className="p-4 border-t border-border space-y-3">
                {loadingMarkdown && (
                  <div className="flex items-center gap-2 py-4 justify-center">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet border-t-transparent" />
                    <span className="font-mono text-xs text-muted">Formatando nota...</span>
                  </div>
                )}

                {markdownError && (
                  <p className="text-xs text-crimson" role="alert">
                    {markdownError}
                  </p>
                )}

                {markdown && (
                  <>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void handleCopyMarkdown()}
                        className="btn-interactive flex-1 rounded border border-border px-3 py-1.5 font-mono text-[10px] uppercase text-muted hover:text-foreground"
                      >
                        {copied ? "Copiado! ✓" : "Copiar Markdown"}
                      </button>
                      <button
                        type="button"
                        disabled={exportingInline}
                        onClick={() => void handleExportInline()}
                        className="btn-interactive flex-1 rounded border border-violet/40 bg-violet-500/10 px-3 py-1.5 font-mono text-[10px] uppercase text-violet-300 hover:bg-violet-500/20"
                      >
                        {exportingInline ? "Gravando..." : "Gravar no Vault"}
                      </button>
                    </div>

                    {exportInlineResult && (
                      <p className="font-mono text-[10px] text-center text-emerald">
                        {exportInlineResult}
                      </p>
                    )}

                    <pre className="rounded-md bg-slate-dark p-3 text-[11px] font-mono text-foreground/90 overflow-x-auto border border-border/80 max-h-64 select-all">
                      {markdown}
                    </pre>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
