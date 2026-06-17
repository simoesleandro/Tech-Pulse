export interface NewsItem {
  id: number;
  title: string;
  title_original: string;
  description: string;
  url: string;
  source: string;
  ai_relevance: string;
  hype_score: number;
  ai_reasoning: string | null;
  is_read: boolean;
  is_bookmarked: boolean;
  folder_id: number | null;
  folder_name: string | null;
  obsidian_exported_at: string | null;
  created_at: string;
}

export interface TopicFolder {
  id: number;
  name: string;
  item_count: number;
  created_at: string;
}

export interface NewsFilters {
  is_read?: boolean;
  is_bookmarked?: boolean;
  ai_relevance?: string;
  folder_id?: number;
  source?: string;
  min_hype?: number;
  hype?: number;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface NewsListResponse {
  items: NewsItem[];
  total: number;
  limit: number;
  offset: number;
}

export type FeedView = "queue" | "read" | "saved";

export interface PipelineStep {
  id: string;
  label: string;
  estimated_seconds: number;
  agent: string | null;
}

export interface PipelineConfig {
  ingest: PipelineStep[];
  backfill: PipelineStep[];
}

export type PipelineStepEvent =
  | {
      type: "step";
      step_id: string;
      status: "active" | "done";
      detail?: string;
      article_index?: number;
      article_total?: number;
    }
  | {
      type: "complete";
      result: IngestResult | EnrichBackfillResult | ObsidianExportResult;
    }
  | {
      type: "error";
      message: string;
    };

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
  remaining: number;
  error_messages?: string[];
}

export interface BulkNewsResult {
  affected: number;
}

export interface BulkNewsUpdatePayload {
  ids: number[];
  is_read?: boolean;
  is_bookmarked?: boolean;
  folder_id?: number | null;
  clear_folder?: boolean;
}

export interface ObsidianExportResult {
  exported: number;
  exported_ids: number[];
  paths: string[];
  mode: string;
  errors: string[];
}

export interface ObsidianFormatResult {
  items: { id: number; markdown: string }[];
  markdown: string;
}

export interface ObsidianStatus {
  configured: boolean;
  mode: string | null;
  folder: string;
  connected: boolean | null;
  message: string | null;
}
