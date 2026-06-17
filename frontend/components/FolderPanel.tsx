"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { createFolder, deleteFolder } from "@/lib/api";
import type { TopicFolder } from "@/lib/types";

interface FolderPanelProps {
  folders: TopicFolder[];
}

export function FolderPanel({ folders: initialFolders }: FolderPanelProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = searchParams.get("view") ?? "queue";
  const activeFolder = searchParams.get("folder");

  const [folders, setFolders] = useState(initialFolders);
  const [newFolderName, setNewFolderName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setFolders(initialFolders);
  }, [initialFolders]);

  if (view !== "saved" && view !== "queue") {
    return null;
  }

  function navigateFolder(folderId: number | null) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("view", view);
    if (folderId === null) {
      params.delete("folder");
    } else {
      params.set("folder", String(folderId));
    }
    router.push(`/?${params.toString()}`);
  }

  async function handleCreateFolder(event: FormEvent) {
    event.preventDefault();
    const name = newFolderName.trim();
    if (!name || isCreating) {
      return;
    }

    setError(null);
    setSuccess(null);
    setIsCreating(true);

    try {
      const folder = await createFolder(name);
      setFolders((current) =>
        [...current, folder].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setNewFolderName("");
      setSuccess(`Pasta "${folder.name}" criada.`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar pasta.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeleteFolder(folderId: number, folderName: string) {
    if (!window.confirm(`Excluir a pasta "${folderName}"? Os artigos permanecem salvos.`)) {
      return;
    }

    setError(null);
    try {
      await deleteFolder(folderId);
      setFolders((current) => current.filter((folder) => folder.id !== folderId));
      if (activeFolder === String(folderId)) {
        navigateFolder(null);
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir pasta.");
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface/60 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-wide text-cyan">
            Pastas por assunto
          </p>
          <p className="mt-1 text-xs text-muted">
            {view === "queue"
              ? "Filtre a fila por pasta ou sem pasta para triagem rápida."
              : "Organize seus salvos em pastas como IA, DevOps, Python, etc."}
          </p>
        </div>

        <form onSubmit={(event) => void handleCreateFolder(event)} className="flex w-full max-w-sm gap-2">
          <input
            type="text"
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            placeholder="Nova pasta…"
            disabled={isCreating}
            className="flex-1 rounded-md border border-border bg-slate-dark px-3 py-2 text-sm text-foreground placeholder:text-muted focus:border-cyan/50 focus:outline-none"
          />
          <button
            type="submit"
            disabled={isCreating || !newFolderName.trim()}
            className="btn-interactive shrink-0 rounded-md border border-cyan/40 bg-cyan/10 px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-cyan"
          >
            {isCreating ? "Criando…" : "Criar"}
          </button>
        </form>
      </div>

      {error ? (
        <p className="mt-2 text-xs text-crimson" role="alert">
          {error}
        </p>
      ) : null}

      {success ? (
        <p className="mt-2 text-xs text-emerald" role="status">
          {success}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => navigateFolder(null)}
          className={`btn-interactive rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-wide ${
            !activeFolder
              ? "border-cyan bg-cyan/10 text-cyan"
              : "border-border text-muted"
          }`}
        >
          {view === "queue" ? "Toda a fila" : "Todos os salvos"}
        </button>

        <button
          type="button"
          onClick={() => navigateFolder(-1)}
          className={`btn-interactive rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-wide ${
            activeFolder === "-1"
              ? "border-cyan bg-cyan/10 text-cyan"
              : "border-border text-muted"
          }`}
        >
          Sem pasta
        </button>

        {folders.map((folder) => (
          <div key={folder.id} className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => navigateFolder(folder.id)}
              className={`btn-interactive rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-wide ${
                activeFolder === String(folder.id)
                  ? "border-cyan bg-cyan/10 text-cyan"
                  : "border-border text-muted"
              }`}
            >
              {folder.name} ({folder.item_count})
            </button>
            <button
              type="button"
              onClick={() => void handleDeleteFolder(folder.id, folder.name)}
              aria-label={`Excluir pasta ${folder.name}`}
              className="btn-interactive rounded-full border border-border px-2 py-1 text-[10px] text-muted hover:text-crimson"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
