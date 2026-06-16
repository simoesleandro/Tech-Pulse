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


class NewsItemCreate(NewsItemBase):
    pass


class NewsItemResponse(NewsItemBase):
    id: int
    title_original: str
    is_read: bool
    is_bookmarked: bool
    folder_id: int | None = None
    folder_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class HealthResponse(BaseModel):
    status: str
    service: str
