from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, engine


class TopicFolder(Base):
    __tablename__ = "topic_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["NewsItem"]] = relationship(back_populates="folder")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    title_original: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    ai_relevance: Mapped[str] = mapped_column(String, nullable=False)
    hype_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    engagement_reactions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    engagement_comments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    engagement_stars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    engagement_ups: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_enriched: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_bookmarked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topic_folders.id"), nullable=True
    )
    obsidian_exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_cache: Mapped[str | None] = mapped_column(String, nullable=True)
    user_relevance: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    folder: Mapped["TopicFolder | None"] = relationship(back_populates="items")

    __table_args__ = (Index("idx_news_unread", "is_read", "ai_relevance"),)


def migrate_sqlite_schema() -> None:
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='news_items'")
        ).fetchall()
        if not tables:
            return

        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(news_items)")).fetchall()
        }

        if "title_original" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN title_original TEXT NOT NULL DEFAULT ''")
            )
        if "description" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            )
        if "hype_score" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN hype_score INTEGER NOT NULL DEFAULT 0")
            )
        if "is_enriched" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN is_enriched INTEGER NOT NULL DEFAULT 0")
            )
        if "engagement_reactions" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE news_items ADD COLUMN engagement_reactions INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "engagement_comments" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE news_items ADD COLUMN engagement_comments INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "engagement_stars" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN engagement_stars INTEGER NOT NULL DEFAULT 0")
            )
        if "engagement_ups" not in columns:
            conn.execute(
                text("ALTER TABLE news_items ADD COLUMN engagement_ups INTEGER NOT NULL DEFAULT 0")
            )
        if "folder_id" not in columns:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN folder_id INTEGER"))
        if "ai_reasoning" not in columns:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN ai_reasoning TEXT"))
        if "obsidian_exported_at" not in columns:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN obsidian_exported_at TEXT"))
        if "content_cache" not in columns:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN content_cache TEXT"))
        if "user_relevance" not in columns:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN user_relevance TEXT"))

        conn.execute(
            text(
                "UPDATE news_items SET title_original = title "
                "WHERE title_original IS NULL OR title_original = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE news_items SET is_enriched = 1 "
                "WHERE description != '' AND title != title_original"
            )
        )
        conn.commit()
