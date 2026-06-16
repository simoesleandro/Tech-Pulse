import { cache } from "react";

import { PAGE_SIZE } from "@/lib/feed-filters";
import { apiJson } from "@/lib/client-api";
import type {
  BulkNewsResult,
  BulkNewsUpdatePayload,
  EnrichBackfillResult,
  FeedView,
  IngestResult,
  NewsFilters,
  NewsItem,
  NewsListResponse,
  ObsidianExportResult,
  ObsidianFormatResult,
  ObsidianStatus,
  PipelineConfig,
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
  if (filters?.source) {
    params.set("source", filters.source);
  }
  if (filters?.min_hype !== undefined) {
    params.set("min_hype", String(filters.min_hype));
  }
  if (filters?.hype !== undefined) {
    params.set("hype", String(filters.hype));
  }
  if (filters?.q) {
    params.set("q", filters.q);
  }
  if (filters?.limit !== undefined) {
    params.set("limit", String(filters.limit));
  }
  if (filters?.offset !== undefined) {
    params.set("offset", String(filters.offset));
  }
  const query = params.toString();
  return `/api/news${query ? `?${query}` : ""}`;
}

function buildNewsCountUrl(filters?: Omit<NewsFilters, "limit" | "offset">): string {
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
  if (filters?.source) {
    params.set("source", filters.source);
  }
  if (filters?.min_hype !== undefined) {
    params.set("min_hype", String(filters.min_hype));
  }
  if (filters?.hype !== undefined) {
    params.set("hype", String(filters.hype));
  }
  if (filters?.q) {
    params.set("q", filters.q);
  }
  const query = params.toString();
  return `/api/news/count${query ? `?${query}` : ""}`;
}

export async function fetchNews(filters?: NewsFilters): Promise<NewsListResponse> {
  return apiJson<NewsListResponse>(buildNewsUrl(filters));
}

export async function fetchNewsCount(
  filters?: Omit<NewsFilters, "limit" | "offset">,
): Promise<number> {
  const response = await apiJson<{ count: number }>(buildNewsCountUrl(filters));
  return response.count;
}

export interface FeedQueryOptions {
  view: FeedView;
  folderId?: number;
  page?: number;
  source?: string;
  hype?: number;
  q?: string;
}

function viewToFilters(
  view: FeedView,
  folderId?: number,
  extra?: Pick<FeedQueryOptions, "source" | "hype" | "q">,
): Omit<NewsFilters, "limit" | "offset"> {
  const filters: Omit<NewsFilters, "limit" | "offset"> = {
    ai_relevance: "RELEVANTE",
  };

  if (view === "read") {
    filters.is_read = true;
  } else if (view === "saved") {
    filters.is_bookmarked = true;
    if (folderId !== undefined) {
      filters.folder_id = folderId;
    }
  } else {
    filters.is_read = false;
  }

  if (extra?.source) {
    filters.source = extra.source;
  }
  if (extra?.hype !== undefined) {
    filters.hype = extra.hype;
  }
  if (extra?.q) {
    filters.q = extra.q;
  }

  return filters;
}

export const getFeedPage = cache(
  async (options: FeedQueryOptions): Promise<NewsListResponse> => {
    const page = Math.max(1, options.page ?? 1);
    const baseFilters = viewToFilters(options.view, options.folderId, options);

    return fetchNews({
      ...baseFilters,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    });
  },
);

export const getUnreadCount = cache(async (): Promise<number> => {
  return fetchNewsCount({ is_read: false, ai_relevance: "RELEVANTE" });
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

export async function fetchPipelineSteps(): Promise<PipelineConfig> {
  return apiJson<PipelineConfig>("/api/pipeline/steps", {
    timeoutMs: 10_000,
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

export async function fetchObsidianStatus(): Promise<ObsidianStatus> {
  return apiJson<ObsidianStatus>("/api/obsidian/status", {
    timeoutMs: 10_000,
  });
}

export async function exportNewsToObsidian(ids: number[]): Promise<ObsidianExportResult> {
  return apiJson<ObsidianExportResult>("/api/obsidian/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
    timeoutMs: 180_000,
  });
}

export async function formatNewsForObsidian(ids: number[]): Promise<ObsidianFormatResult> {
  return apiJson<ObsidianFormatResult>("/api/obsidian/format", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
    timeoutMs: 180_000,
  });
}
