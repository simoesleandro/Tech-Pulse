"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { PAGE_SIZE } from "@/lib/feed-filters";

interface FeedPaginationProps {
  total: number;
  page: number;
}

function pageHref(pathname: string, searchParams: URLSearchParams, page: number): string {
  const params = new URLSearchParams(searchParams.toString());
  if (page <= 1) {
    params.delete("page");
  } else {
    params.set("page", String(page));
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function FeedPagination({ total, page }: FeedPaginationProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const hasPrev = safePage > 1;
  const hasNext = safePage < totalPages;

  if (total <= PAGE_SIZE) {
    return null;
  }

  const from = (safePage - 1) * PAGE_SIZE + 1;
  const to = Math.min(safePage * PAGE_SIZE, total);

  return (
    <nav
      aria-label="Paginação do feed"
      className="flex flex-col items-center gap-3 pt-2"
    >
      <p className="font-mono text-[10px] uppercase tracking-wide text-muted">
        {from}–{to} de {total} · página {safePage} de {totalPages}
      </p>

      <div className="flex items-center gap-3">
        {hasPrev ? (
          <Link
            href={pageHref(pathname, searchParams, safePage - 1)}
            className="btn-interactive flex h-10 w-10 items-center justify-center rounded-full border border-border text-muted hover:border-cyan/50 hover:text-cyan"
            aria-label="Página anterior"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M10 3L5 8l5 5" />
            </svg>
          </Link>
        ) : (
          <span
            className="flex h-10 w-10 items-center justify-center rounded-full border border-border/40 text-muted/30"
            aria-hidden="true"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10 3L5 8l5 5" />
            </svg>
          </span>
        )}

        {hasNext ? (
          <Link
            href={pageHref(pathname, searchParams, safePage + 1)}
            className="btn-interactive flex h-10 w-10 items-center justify-center rounded-full border border-cyan/40 bg-cyan/10 text-cyan hover:border-cyan hover:bg-cyan/20"
            aria-label="Próxima página"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M6 3l5 5-5 5" />
            </svg>
          </Link>
        ) : (
          <span
            className="flex h-10 w-10 items-center justify-center rounded-full border border-border/40 text-muted/30"
            aria-hidden="true"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 3l5 5-5 5" />
            </svg>
          </span>
        )}
      </div>
    </nav>
  );
}
