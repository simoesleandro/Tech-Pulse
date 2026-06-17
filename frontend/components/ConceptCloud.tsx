"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchObsidianConcepts } from "@/lib/api";
import type { ObsidianConcept } from "@/lib/types";

export function ConceptCloud() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [concepts, setConcepts] = useState<ObsidianConcept[]>([]);
  const [isPending, startTransition] = useTransition();

  const activeQ = searchParams.get("q") || "";

  useEffect(() => {
    // Load concepts on mount and update when search parameters change (which could indicate exports completed)
    fetchObsidianConcepts()
      .then(setConcepts)
      .catch(() => {
        /* silent fallback */
      });
  }, [searchParams]);

  if (concepts.length === 0) {
    return null;
  }

  function handleConceptClick(concept: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("q", concept);
    params.set("page", "1"); // reset page
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });
  }

  function handleClearFilter() {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("q");
    params.set("page", "1");
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });
  }

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between border-b border-border/40 pb-2 mb-3">
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-wide text-violet-300">
          <svg className="h-4 w-4 text-violet" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
          </svg>
          <span>Grafo de Conhecimento — Vault</span>
        </div>
        {activeQ && (
          <button
            type="button"
            onClick={handleClearFilter}
            disabled={isPending}
            className="font-mono text-[10px] text-crimson hover:underline"
          >
            Limpar Filtro ({activeQ})
          </button>
        )}
      </div>

      <p className="text-xs text-muted mb-4">
        Conceitos técnicos e tags mais frequentes nas suas notas exportadas ao Obsidian. Clique para filtrar.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-2.5 py-2">
        {concepts.map((item) => {
          const isActive = activeQ.toLowerCase() === item.concept.toLowerCase();
          
          // Determine size and styling based on tag occurrence frequency
          let tagClass = "px-2.5 py-1 text-xs text-muted bg-surface/40 hover:bg-cyan/10 hover:text-cyan border border-border/30";
          if (item.count >= 6) {
            tagClass = "px-3.5 py-1.5 text-sm font-bold text-cyan bg-cyan/10 border border-cyan/45 hover:bg-cyan/20 hover:text-cyan-300 shadow-sm shadow-cyan/5";
          } else if (item.count >= 3) {
            tagClass = "px-3 py-1 text-xs font-semibold text-cyan/80 bg-cyan/5 border border-cyan/20 hover:bg-cyan/10 hover:text-cyan";
          } else if (item.count === 2) {
            tagClass = "px-2.5 py-1 text-xs text-slate-300 bg-surface/70 border border-border/50 hover:bg-cyan/10 hover:text-cyan";
          }

          if (isActive) {
            tagClass = "px-3.5 py-1.5 text-sm font-bold text-slate-900 bg-cyan border border-cyan shadow-md shadow-cyan/25 cursor-default";
          }

          return (
            <button
              key={item.concept}
              type="button"
              disabled={isPending || isActive}
              onClick={() => handleConceptClick(item.concept)}
              className={`rounded-xl transition-all duration-200 cursor-pointer touch-manipulation ${tagClass}`}
            >
              <span>{item.concept}</span>
              <span className={`ml-1.5 font-mono text-[9px] ${isActive ? "text-slate-800" : "text-muted/80"}`}>
                ({item.count})
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
