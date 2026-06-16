import { cache } from "react";

import { apiJson } from "@/lib/client-api";
import type {
  BulkNewsResult,
  BulkNewsUpdatePayload,
  EnrichBackfillResult,
  FeedView,
  IngestResult,
  NewsFilters,
  NewsItem,
  SeedResult,
  TopicFolder,
} from "@/lib/types";

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
  if (filters?.folder_id !== undefined) {
    params.set("folder_id", String(filters.folder_id));
  }
  const query = params.toString();
  return `/api/news${query ? `?${query}` : ""}`;
}

export async function fetchNews(filters?: NewsFilters): Promise<NewsItem[]> {
  return apiJson<NewsItem[]>(buildNewsUrl(filters));
}

export const getFeedItems = cache(async (view: FeedView, folderId?: number): Promise<NewsItem[]> => {
  if (view === "read") {
    return fetchNews({ is_read: true, ai_relevance: "RELEVANTE" });
  }

  if (view === "saved") {
    const filters: NewsFilters = { is_bookmarked: true, ai_relevance: "RELEVANTE" };
    if (folderId !== undefined) {
      filters.folder_id = folderId;
    }
    return fetchNews(filters);
  }

  return fetchNews({ is_read: false, ai_relevance: "RELEVANTE" });
});

export async function fetchFolders(): Promise<TopicFolder[]> {
  return apiJson<TopicFolder[]>("/api/folders");
}

export async function createFolder(name: string): Promise<TopicFolder> {
  return apiJson<TopicFolder>("/api/folders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    timeoutMs: 15_000,
  });
}

export async function deleteFolder(folderId: number): Promise<BulkNewsResult> {
  return apiJson<BulkNewsResult>(`/api/folders/${folderId}`, {
    method: "DELETE",
    timeoutMs: 15_000,
  });
}

export async function assignNewsFolder(
  id: number,
  folderId: number | null,
): Promise<NewsItem> {
  return apiJson<NewsItem>(`/api/news/${id}/folder`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_id: folderId }),
    timeoutMs: 15_000,
  });
}

export async function patchReadStatus(id: number, is_read: boolean): Promise<NewsItem> {
  return apiJson<NewsItem>(`/api/news/${id}/read`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_read }),
    timeoutMs: 15_000,
  });
}

export async function patchBookmarkStatus(
  id: number,
  is_bookmarked: boolean,
): Promise<NewsItem> {
  return apiJson<NewsItem>(`/api/news/${id}/bookmark`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_bookmarked }),
    timeoutMs: 15_000,
  });
}

export async function triggerIngest(): Promise<IngestResult> {
  return apiJson<IngestResult>("/api/ingest", {
    method: "POST",
    timeoutMs: 600_000,
  });
}

export async function seedDemoData(): Promise<SeedResult> {
  return apiJson<SeedResult>("/api/seed", {
    method: "POST",
    timeoutMs: 15_000,
  });
}

export async function enrichBackfill(limit = 1): Promise<EnrichBackfillResult> {
  return apiJson<EnrichBackfillResult>(`/api/enrich-backfill?limit=${limit}`, {
    method: "POST",
    timeoutMs: 300_000,
  });
}

export async function deleteNewsItem(id: number): Promise<BulkNewsResult> {
  return apiJson<BulkNewsResult>(`/api/news/${id}`, {
    method: "DELETE",
    timeoutMs: 15_000,
  });
}

export async function bulkDeleteNews(ids: number[]): Promise<BulkNewsResult> {
  return apiJson<BulkNewsResult>("/api/news/bulk", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
    timeoutMs: 30_000,
  });
}

export async function bulkUpdateNews(
  payload: BulkNewsUpdatePayload,
): Promise<BulkNewsResult> {
  return apiJson<BulkNewsResult>("/api/news/bulk", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    timeoutMs: 30_000,
  });
}
