"use client";

import { useEffect, useState, useTransition } from "react";
import { fetchSettings, updateSettings } from "@/lib/api";
import type { AppSettings } from "@/lib/types";

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!open) {
      return;
    }
    // Load current settings when the panel is opened
    fetchSettings()
      .then((data) => {
        setSettings(data);
        setError(null);
      })
      .catch((err) => {
        setError("Não foi possível carregar as configurações do backend.");
      });
  }, [open]);

  function handleToggleBackground() {
    if (!settings) return;
    setSettings({
      ...settings,
      background_ingest_enabled: !settings.background_ingest_enabled,
    });
    setSuccessMessage(null);
  }

  function handleToggleSource(sourceKey: keyof AppSettings["sources"]) {
    if (!settings) return;
    setSettings({
      ...settings,
      sources: {
        ...settings.sources,
        [sourceKey]: !settings.sources[sourceKey],
      },
    });
    setSuccessMessage(null);
  }

  function handleSave() {
    if (!settings) return;
    setSuccessMessage(null);
    setError(null);

    startTransition(async () => {
      try {
        const updated = await updateSettings(settings);
        setSettings(updated);
        setSuccessMessage("Configurações salvas e aplicadas com sucesso!");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao salvar as configurações.");
      }
    });
  }

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 font-mono text-xs uppercase tracking-wide text-cyan hover:underline"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>{open ? "Ocultar Configurações" : "Configurações de Ingestão"}</span>
        </button>
      </div>

      {open && (
        <div className="mt-4 flex flex-col gap-4 border-t border-border/40 pt-4 animate-in fade-in duration-200">
          {settings ? (
            <>
              {/* Background ingest toggle */}
              <div className="flex items-center justify-between gap-4 rounded-lg bg-surface/50 p-3 border border-border/30">
                <div className="space-y-1">
                  <span className="block text-sm font-semibold text-foreground">
                    Agendador em Segundo Plano
                  </span>
                  <span className="block text-xs text-muted">
                    Executa a busca por novos artigos no backend automaticamente.
                  </span>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    checked={settings.background_ingest_enabled}
                    onChange={handleToggleBackground}
                    disabled={isPending}
                    className="peer sr-only"
                  />
                  <div className="peer h-6 w-11 rounded-full bg-slate-700 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-cyan peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none" />
                </label>
              </div>

              {/* Source configuration */}
              <div className="space-y-2">
                <span className="block font-mono text-[10px] uppercase tracking-wide text-muted">
                  Fontes de Ingestão Ativas
                </span>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    { key: "dev_to", label: "dev.to" },
                    { key: "reddit", label: "Reddit" },
                    { key: "github_trends", label: "GitHub Trends" },
                    { key: "hacker_news", label: "Hacker News" },
                    { key: "rss_feeds", label: "RSS Feeds" },
                  ].map((src) => (
                    <label
                      key={src.key}
                      className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/40 bg-surface/30 px-3 py-2 text-sm text-foreground hover:bg-surface/50 transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={settings.sources[src.key as keyof AppSettings["sources"]]}
                        onChange={() => handleToggleSource(src.key as keyof AppSettings["sources"])}
                        disabled={isPending}
                        className="h-4 w-4 rounded border-border bg-slate-800 text-cyan accent-cyan"
                      />
                      <span>{src.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Save actions */}
              <div className="flex items-center gap-3 border-t border-border/40 pt-4">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isPending}
                  className="btn-interactive btn-primary rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan disabled:opacity-50"
                >
                  {isPending ? "Salvando…" : "Salvar Configurações"}
                </button>
              </div>
            </>
          ) : (
            <div className="flex justify-center py-4">
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan" />
            </div>
          )}

          {error && (
            <p className="text-xs text-crimson" role="alert">
              {error}
            </p>
          )}

          {successMessage && (
            <p className="font-mono text-xs text-emerald" role="status">
              {successMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
