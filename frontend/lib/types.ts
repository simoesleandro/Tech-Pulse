export interface NewsItem {
  id: number;
  title: string;
  title_original: string;
  description: string;
  url: string;
  source: string;
  ai_relevance: string;
  hype_score: number;
  is_read: boolean;
  is_bookmarked: boolean;
  created_at: string;
}

export interface NewsFilters {
  is_read?: boolean;
  is_bookmarked?: boolean;
  ai_relevance?: string;
}

export type FeedView = "queue" | "read" | "saved";

export interface IngestResult {
  fetched: number;
  skipped_duplicate: number;
  classified: number;
  saved: number;
  relevante: number;
  lixo: number;
  errors: string[];
}

export interface SeedResult {
  created: number;
  skipped: number;
  total: number;
}

export interface EnrichBackfillResult {
  processed: number;
  errors: number;
  candidates: number;
}
