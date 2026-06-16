"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import type { FeedView } from "@/lib/types";

const VIEWS: { id: FeedView; label: string }[] = [
  { id: "queue", label: "Fila" },
  { id: "read", label: "Lidas" },
  { id: "saved", label: "Salvos" },
];

export function FilterBar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeView = (searchParams.get("view") as FeedView) || "queue";

  return (
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
    </nav>
  );
}
