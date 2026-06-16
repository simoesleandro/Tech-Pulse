"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { enrichBackfill, seedDemoData, triggerIngest } from "@/lib/api";
import type { EnrichBackfillResult, IngestResult, SeedResult } from "@/lib/types";

export function IngestPanel() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null);
  const [backfillResult, setBackfillResult] = useState<EnrichBackfillResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleIngest() {
    setError(null);
    setIngestResult(null);
    setSeedResult(null);
    setBackfillResult(null);

    startTransition(async () => {
      try {
        const stats = await triggerIngest();
        setIngestResult(stats);
        router.refresh();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Erro desconhecido na ingestão.",
        );
      }
    });
  }

  function handleSeed() {
    setError(null);
    setIngestResult(null);
    setSeedResult(null);
    setBackfillResult(null);

    startTransition(async () => {
      try {
        const stats = await seedDemoData();
        setSeedResult(stats);
        router.refresh();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Erro desconhecido ao carregar demo.",
        );
      }
    });
  }

  function handleBackfill() {
    setError(null);
    setIngestResult(null);
    setSeedResult(null);
    setBackfillResult(null);

    startTransition(async () => {
      try {
        const stats = await enrichBackfill();
        setBackfillResult(stats);
        router.refresh();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Erro ao traduzir artigos pendentes.",
        );
      }
    });
  }

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-cyan">
            Ingestão
          </p>
          <p className="mt-1 text-sm text-muted">
            Busca novas fontes, classifica via Ollama, traduz para PT-BR e calcula hype da comunidade.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleBackfill}
            disabled={isPending}
            className="rounded-md border border-border px-4 py-2 font-mono text-xs uppercase tracking-wide text-muted transition-colors hover:border-cyan/40 hover:text-cyan focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:cursor-not-allowed disabled:opacity-50"
          >
            Traduzir pendentes
          </button>
          <button
            type="button"
            onClick={handleSeed}
            disabled={isPending}
            className="rounded-md border border-border px-4 py-2 font-mono text-xs uppercase tracking-wide text-muted transition-colors hover:border-cyan/40 hover:text-cyan focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:cursor-not-allowed disabled:opacity-50"
          >
            Carregar demo
          </button>
          <button
            type="button"
            onClick={handleIngest}
            disabled={isPending}
            className="rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan transition-colors hover:bg-cyan/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isPending ? "Processando…" : "Atualizar feed"}
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-3 text-sm text-crimson" role="alert">
          {error}
        </p>
      ) : null}

      {ingestResult ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {ingestResult.saved} salvas · {ingestResult.relevante} relevantes ·{" "}
          {ingestResult.skipped_duplicate} duplicadas ignoradas
          {ingestResult.errors.length > 0
            ? ` · ${ingestResult.errors.length} erros`
            : null}
        </p>
      ) : null}

      {seedResult ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {seedResult.created} artigos criados · {seedResult.skipped} ignorados
        </p>
      ) : null}

      {backfillResult ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {backfillResult.processed} artigos traduzidos · {backfillResult.errors} erros
        </p>
      ) : null}
    </div>
  );
}
