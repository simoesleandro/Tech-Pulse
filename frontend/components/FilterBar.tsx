"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import {
  HYPE_FILTERS,
  SOURCE_FILTERS,
  TOPIC_FILTERS,
} from "@/lib/feed-filters";
import type { FeedView } from "@/lib/types";

const VIEWS: { id: FeedView; label: string }[] = [
  { id: "queue", label: "Fila" },
  { id: "read", label: "Lidas" },
  { id: "saved", label: "Salvos" },
];

function buildHref(
  pathname: string,
  searchParams: URLSearchParams,
  updates: Record<string, string | null>,
): string {
  const params = new URLSearchParams(searchParams.toString());

  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === "") {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }

  params.delete("page");

  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function FilterChip({
  href,
  active,
  label,
}: {
  href: string;
  active: boolean;
  label: string;
}) {
  return (
    <Link
      href={href}
      className={`nav-link-interactive rounded-md border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan ${
        active
          ? "border-cyan bg-cyan/10 text-cyan"
          : "border-border text-muted hover:border-cyan/50 hover:text-cyan"
      }`}
      aria-current={active ? "true" : undefined}
    >
      {label}
    </Link>
  );
}

function SearchField() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeQ = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(activeQ);

  useEffect(() => {
    setQuery(activeQ);
  }, [activeQ]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams(searchParams.toString());
    const trimmed = query.trim();
    if (trimmed) {
      params.set("q", trimmed);
    } else {
      params.delete("q");
    }
    params.delete("page");
    const next = params.toString();
    router.push(next ? `${pathname}?${next}` : pathname);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <p className="font-mono text-[10px] uppercase tracking-wide text-muted/80">
        Buscar no feed
      </p>
      <div className="flex gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Título, descrição, tecnologia…"
          className="min-w-0 flex-1 rounded-md border border-border bg-slate-dark px-3 py-2 font-mono text-xs text-foreground placeholder:text-muted/60 focus:border-cyan/50 focus:outline-none"
        />
        <button
          type="submit"
          className="btn-interactive shrink-0 rounded-md border border-cyan/40 bg-cyan/10 px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-cyan"
        >
          Buscar
        </button>
      </div>
    </form>
  );
}

function FilterPanel() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeSource = searchParams.get("source") ?? "";
  const activeQ = searchParams.get("q") ?? "";
  const activeHype = searchParams.get("hype") ?? "";

  const topicFromQ = TOPIC_FILTERS.some((topic) => topic.id === activeQ)
    ? activeQ
    : "";

  const hasFilters = Boolean(activeSource || activeQ || activeHype);

  return (
    <section
      aria-label="Opções de filtro"
      className="flex flex-col gap-3 rounded-lg border border-border/80 bg-surface/40 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted">
          Refinar feed
        </p>
        {hasFilters ? (
          <Link
            href={buildHref(pathname, searchParams, {
              source: null,
              q: null,
              hype: null,
            })}
            className="font-mono text-[10px] uppercase tracking-wide text-cyan hover:underline"
          >
            Limpar filtros
          </Link>
        ) : null}
      </div>

      <SearchField />

      <div className="flex flex-col gap-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted/80">
          Fonte
        </p>
        <div className="flex flex-wrap gap-1.5">
          <FilterChip
            href={buildHref(pathname, searchParams, { source: null })}
            active={!activeSource}
            label="Todas"
          />
          {SOURCE_FILTERS.map((source) => (
            <FilterChip
              key={source.id}
              href={buildHref(pathname, searchParams, {
                source: activeSource === source.id ? null : source.id,
              })}
              active={activeSource === source.id}
              label={source.label}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted/80">
          Hype (estrelas exatas)
        </p>
        <div className="flex flex-wrap gap-1.5">
          {HYPE_FILTERS.map((option) => (
            <FilterChip
              key={option.id || "any"}
              href={buildHref(pathname, searchParams, {
                hype: activeHype === option.id ? null : option.id || null,
              })}
              active={activeHype === option.id}
              label={option.label}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-muted/80">
          Assunto / stack
        </p>
        <div className="flex flex-wrap gap-1.5">
          {TOPIC_FILTERS.map((topic) => (
            <FilterChip
              key={topic.id}
              href={buildHref(pathname, searchParams, {
                q: topicFromQ === topic.id ? null : topic.id,
              })}
              active={topicFromQ === topic.id}
              label={topic.label}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export function FilterBar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeView = (searchParams.get("view") as FeedView) || "queue";
  const [filtersOpen, setFiltersOpen] = useState(false);

  const hasActiveFilters = Boolean(
    searchParams.get("source") ||
      searchParams.get("q") ||
      searchParams.get("hype"),
  );

  return (
    <div className="flex flex-col gap-3">
      <nav
        aria-label="Filtrar feed"
        className="flex flex-wrap items-center gap-2"
      >
        {VIEWS.map((view) => {
          const isActive = activeView === view.id;
          const params = new URLSearchParams(searchParams.toString());
          params.set("view", view.id);
          const href = `${pathname}?${params.toString()}`;

          return (
            <Link
              key={view.id}
              href={href}
              className={`nav-link-interactive rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-wide focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan ${
                isActive
                  ? "border-cyan bg-cyan/10 text-cyan shadow-[0_4px_14px_rgba(6,182,212,0.2)]"
                  : "border-border text-muted hover:border-cyan/50 hover:bg-cyan/5 hover:text-cyan"
              }`}
              aria-current={isActive ? "page" : undefined}
            >
              {view.label}
            </Link>
          );
        })}

        <button
          type="button"
          onClick={() => setFiltersOpen((current) => !current)}
          aria-expanded={filtersOpen}
          className={`nav-link-interactive rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-wide focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan ${
            filtersOpen || hasActiveFilters
              ? "border-cyan bg-cyan/10 text-cyan"
              : "border-border text-muted hover:border-cyan/50 hover:bg-cyan/5 hover:text-cyan"
          }`}
        >
          Filtros
          {hasActiveFilters ? (
            <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-cyan" />
          ) : null}
        </button>
      </nav>

      {filtersOpen ? <FilterPanel /> : null}
    </div>
  );
}
