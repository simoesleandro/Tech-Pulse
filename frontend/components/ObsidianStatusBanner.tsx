"use client";

import { useEffect, useState } from "react";

import { fetchObsidianStatus } from "@/lib/api";
import type { ObsidianStatus } from "@/lib/types";

export function ObsidianStatusBanner() {
  const [status, setStatus] = useState<ObsidianStatus | null>(null);

  useEffect(() => {
    void fetchObsidianStatus()
      .then(setStatus)
      .catch(() => {
        setStatus(null);
      });
  }, []);

  if (!status) {
    return null;
  }

  if (status.configured && status.connected) {
    const modeLabel =
      status.mode === "filesystem"
        ? "gravação direta no vault"
        : `REST API (${status.mode})`;
    return (
      <p className="font-mono text-[10px] text-emerald">
        Obsidian conectado — {modeLabel} · pasta{" "}
        <span className="text-cyan">{status.folder}/</span>
      </p>
    );
  }

  return (
    <div
      className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-200"
      role="status"
    >
      <p className="font-mono text-[10px] uppercase tracking-wide text-amber-300">
        Obsidian
      </p>
      <p className="mt-1 text-muted">{status.message}</p>
      <p className="mt-2 text-[11px] text-muted">
        Instale o plugin <strong className="text-foreground">Local REST API</strong> no
        Obsidian, copie a API key e configure{" "}
        <code className="text-cyan">OBSIDIAN_REST_API_KEY</code> no{" "}
        <code className="text-cyan">backend/.env</code>.
      </p>
    </div>
  );
}
