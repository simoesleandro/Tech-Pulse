from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

_FTS5_SETUP_SQL = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS news_fts
    USING fts5(
        title,
        title_original,
        description,
        ai_reasoning,
        content='news_items',
        content_rowid='id'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS news_items_ai
    AFTER INSERT ON news_items BEGIN
        INSERT INTO news_fts(rowid, title, title_original, description, ai_reasoning)
        VALUES (new.id, new.title, new.title_original, new.description, COALESCE(new.ai_reasoning, ''));
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS news_items_ad
    AFTER DELETE ON news_items BEGIN
        INSERT INTO news_fts(news_fts, rowid, title, title_original, description, ai_reasoning)
        VALUES ('delete', old.id, old.title, old.title_original, old.description, COALESCE(old.ai_reasoning, ''));
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS news_items_au
    AFTER UPDATE ON news_items BEGIN
        INSERT INTO news_fts(news_fts, rowid, title, title_original, description, ai_reasoning)
        VALUES ('delete', old.id, old.title, old.title_original, old.description, COALESCE(old.ai_reasoning, ''));
        INSERT INTO news_fts(rowid, title, title_original, description, ai_reasoning)
        VALUES (new.id, new.title, new.title_original, new.description, COALESCE(new.ai_reasoning, ''));
    END
    """,
]


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        for stmt in _FTS5_SETUP_SQL:
            conn.execute(text(stmt))
        conn.commit()
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    from app.deps import auth

    original_api_key = auth.API_KEY
    auth.API_KEY = ""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    auth.API_KEY = original_api_key
