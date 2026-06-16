export interface NewsItem {
  id: number;
  title: string;
  url: string;
  source: string;
  ai_relevance: string;
  is_read: boolean;
  is_bookmarked: boolean;
  created_at: string;
}

export interface NewsFilters {
  is_read?: boolean;
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
