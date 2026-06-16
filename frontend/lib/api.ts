import { cache } from "react";

import type { EnrichBackfillResult, FeedView, IngestResult, NewsFilters, NewsItem, SeedResult } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildNewsUrl(filters?: NewsFilters): string {
  const params = new URLSearchParams();
  if (filters?.is_read !== undefined) {
    params.set("is_read", String(filters.is_read));
  }
  if (filters?.is_bookmarked !== undefined) {
    params.set("is_bookmarked", String(filters.is_bookmarked));
  }
  if (filters?.ai_relevance) {
    params.set("ai_relevance", filters.ai_relevance);
  }
  const query = params.toString();
  return `${API_BASE}/api/news${query ? `?${query}` : ""}`;
}

export async function fetchNews(filters?: NewsFilters): Promise<NewsItem[]> {
  const response = await fetch(buildNewsUrl(filters), {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Não foi possível carregar o feed.");
  }

  return response.json();
}

export const getFeedItems = cache(async (view: FeedView): Promise<NewsItem[]> => {
  if (view === "read") {
    return fetchNews({ is_read: true, ai_relevance: "RELEVANTE" });
  }

  if (view === "saved") {
    return fetchNews({ is_bookmarked: true, ai_relevance: "RELEVANTE" });
  }

  return fetchNews({ is_read: false, ai_relevance: "RELEVANTE" });
});

export async function patchReadStatus(
  id: number,
  is_read: boolean,
): Promise<NewsItem> {
  const response = await fetch(`${API_BASE}/api/news/${id}/read`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_read }),
  });

  if (!response.ok) {
    throw new Error("Não foi possível atualizar o status de leitura.");
  }

  return response.json();
}

export async function patchBookmarkStatus(
  id: number,
  is_bookmarked: boolean,
): Promise<NewsItem> {
  const response = await fetch(`${API_BASE}/api/news/${id}/bookmark`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_bookmarked }),
  });

  if (!response.ok) {
    throw new Error("Não foi possível atualizar o favorito.");
  }

  return response.json();
}

export async function triggerIngest(): Promise<IngestResult> {
  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("A ingestão falhou. Verifique se o backend e o Ollama estão ativos.");
  }

  return response.json();
}

export async function seedDemoData(): Promise<SeedResult> {
  const response = await fetch(`${API_BASE}/api/seed`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Não foi possível carregar os dados de demonstração.");
  }

  return response.json();
}

export async function enrichBackfill(): Promise<EnrichBackfillResult> {
  const response = await fetch(`${API_BASE}/api/enrich-backfill`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Não foi possível traduzir os artigos pendentes.");
  }

  return response.json();
}
