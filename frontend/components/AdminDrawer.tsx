"use client";

import { useState } from "react";

import { IngestPanel } from "@/components/IngestPanel";
import { SettingsPanel } from "@/components/SettingsPanel";
import { SystemPanel } from "@/components/SystemPanel";
import {
  pipelineJobLabel,
  usePipelineStatus,
} from "@/hooks/usePipelineStatus";

export function AdminDrawer() {
  const [open, setOpen] = useState(false);
  const pipelineStatus = usePipelineStatus(open);

  const pipelineNotice =
    pipelineStatus.busy && pipelineStatus.active_job
      ? `${pipelineJobLabel(pipelineStatus.active_job)} em andamento — aguarde ou cancele antes de iniciar outra operação.`
      : null;

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
        <div className="flex items-center gap-2">
          {pipelineStatus.busy && pipelineStatus.active_job ? (
            <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-200">
              {pipelineJobLabel(pipelineStatus.active_job)}
            </span>
          ) : null}
          <span className="font-mono text-xs text-muted">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open ? (
        <div className="flex flex-col gap-4 border-t border-border px-4 pb-4 pt-2">
          {pipelineNotice ? (
            <p className="rounded-md border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-xs text-amber-100/90" role="status">
              {pipelineNotice}
            </p>
          ) : null}
          <IngestPanel pipelineStatus={pipelineStatus} />
          <SettingsPanel />
          <SystemPanel pipelineStatus={pipelineStatus} />
        </div>
      ) : null}
    </div>
  );
}
