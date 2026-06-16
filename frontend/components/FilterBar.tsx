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
            className={`rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-wide transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan ${
              isActive
                ? "border-cyan bg-cyan/10 text-cyan"
                : "border-border text-muted hover:border-cyan/40 hover:text-foreground"
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
