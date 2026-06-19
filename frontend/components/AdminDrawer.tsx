"use client";

import { useState } from "react";

import { IngestPanel } from "@/components/IngestPanel";
import { SettingsPanel } from "@/components/SettingsPanel";
import { SystemPanel } from "@/components/SystemPanel";

export function AdminDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-surface-elevated">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-cyan">
            Administração
          </p>
          <p className="mt-0.5 text-sm text-muted">
            Ingestão, configurações e ferramentas do sistema
          </p>
        </div>
        <span className="font-mono text-xs text-muted">{open ? "▲" : "▼"}</span>
      </button>

      {open ? (
        <div className="flex flex-col gap-4 border-t border-border px-4 pb-4 pt-2">
          <IngestPanel />
          <SettingsPanel />
          <SystemPanel />
        </div>
      ) : null}
    </div>
  );
}
