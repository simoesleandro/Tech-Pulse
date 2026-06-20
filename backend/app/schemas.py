from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NewsItemBase(BaseModel):
    title: str
    title_original: str | None = None
    description: str = ""
    url: str
    source: str
    ai_relevance: str
    hype_score: int = 0
    ai_reasoning: str | None = None


class NewsItemCreate(NewsItemBase):
    pass


class NewsItemResponse(NewsItemBase):
    id: int
    title_original: str
    is_read: bool
    is_bookmarked: bool
    user_relevance: str | None = None
    folder_id: int | None = None
    folder_name: str | None = None
    obsidian_exported_at: datetime | None = None
    engagement_reactions: int = 0
    engagement_comments: int = 0
    engagement_stars: int = 0
    engagement_ups: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsListResponse(BaseModel):
    items: list[NewsItemResponse]
    total: int
    limit: int
    offset: int


class NewsCountResponse(BaseModel):
    count: int


class NewsItemFolderUpdate(BaseModel):
    folder_id: int | None = None


class TopicFolderCreate(BaseModel):
    name: str


class TopicFolderResponse(BaseModel):
    id: int
    name: str
    item_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsItemReadUpdate(BaseModel):
    is_read: bool


class NewsItemBookmarkUpdate(BaseModel):
    is_bookmarked: bool


class PipelineStepResponse(BaseModel):
    id: str
    label: str
    estimated_seconds: int
    agent: str | None = None


class PipelineConfigResponse(BaseModel):
    ingest: list[PipelineStepResponse]
    backfill: list[PipelineStepResponse]


class PipelineStatusResponse(BaseModel):
    busy: bool
    active_job: str | None = None


class IngestResult(BaseModel):
    fetched: int
    skipped_duplicate: int
    classified: int
    saved: int
    relevante: int
    lixo: int
    errors: list[str]


class SeedResult(BaseModel):
    created: int
    skipped: int
    total: int


class EnrichBackfillResult(BaseModel):
    processed: int
    errors: int
    candidates: int
    remaining: int
    error_messages: list[str] = []


class BulkNewsUpdate(BaseModel):
    ids: list[int]
    is_read: bool | None = None
    is_bookmarked: bool | None = None
    folder_id: int | None = None
    clear_folder: bool = False


class BulkNewsDelete(BaseModel):
    ids: list[int]


class BulkNewsResult(BaseModel):
    affected: int


class ObsidianBackfillResult(BaseModel):
    discovered: int
    updated: int
    already_marked: int
    missing_in_db: int = 0


class ObsidianMocsResult(BaseModel):
    created: int
    updated: int
    paths: list[str] = []


class ObsidianMigrateResult(BaseModel):
    migrated: int
    skipped: int
    errors: list[str] = []
    removed_empty_dirs: int = 0
    retitled: int = 0
    organized: int = 0


class BackfillStatusResponse(BaseModel):
    obsidian_unmarked: int
    legacy_enrichment_pending: int


class ObsidianExportRequest(BaseModel):
    ids: list[int]


class ObsidianExportResult(BaseModel):
    exported: int
    exported_ids: list[int] = []
    paths: list[str]
    mode: str
    errors: list[str] = []
    skipped: int = 0


class ObsidianFormattedItem(BaseModel):
    id: int
    markdown: str


class ObsidianFormatResult(BaseModel):
    items: list[ObsidianFormattedItem]
    markdown: str


class ObsidianStatusResponse(BaseModel):
    configured: bool
    mode: str | None = None
    folder: str
    connected: bool | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class ObsidianDigestResponse(BaseModel):
    created: bool
    path: str


class SourcesSettings(BaseModel):
    dev_to: bool
    reddit: bool
    github_trends: bool
    hacker_news: bool
    rss_feeds: bool


class AppSettings(BaseModel):
    background_ingest_enabled: bool
    obsidian_auto_export: bool = False
    pipeline_mode: str = "unified"
    sources: SourcesSettings


class ObsidianConceptResponse(BaseModel):
    concept: str
    count: int


class ScraperHealthResponse(BaseModel):
    source: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_items_found: int = 0
    last_error: str | None = None
    status: str  # "ok" | "error" | "never_run"


class SystemHealthResponse(BaseModel):
    scrapers: list[ScraperHealthResponse]
    total_items: int
    relevant_items: int



