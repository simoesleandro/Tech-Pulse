from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, engine


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
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_bookmarked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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

        conn.execute(
            text(
                "UPDATE news_items SET title_original = title "
                "WHERE title_original IS NULL OR title_original = ''"
            )
        )
        conn.commit()
