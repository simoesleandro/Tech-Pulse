"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { triggerIngest } from "@/lib/api";
import type { IngestResult } from "@/lib/types";

export function IngestPanel() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleIngest() {
    setError(null);
    setResult(null);

    startTransition(async () => {
      try {
        const stats = await triggerIngest();
        setResult(stats);
        router.refresh();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Erro desconhecido na ingestão.",
        );
      }
    });
  }

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-cyan">
            Ingestão
          </p>
          <p className="mt-1 text-sm text-muted">
            Busca novas fontes, classifica via Ollama e atualiza o feed.
          </p>
        </div>
        <button
          type="button"
          onClick={handleIngest}
          disabled={isPending}
          className="shrink-0 rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan transition-colors hover:bg-cyan/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPending ? "Processando…" : "Atualizar feed"}
        </button>
      </div>

      {error ? (
        <p className="mt-3 text-sm text-crimson" role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {result.saved} salvas · {result.relevante} relevantes ·{" "}
          {result.skipped_duplicate} duplicadas ignoradas
          {result.errors.length > 0
            ? ` · ${result.errors.length} erros`
            : null}
        </p>
      ) : null}
    </div>
  );
}
