import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from app.config import get_app_config
from app.database import Base, SessionLocal, engine
from app.deps.pipeline_lock import end_pipeline_job, try_begin_pipeline_job
from app.models import migrate_sqlite_schema
from app.services.hype_backfill import backfill_missing_hype
from app.services.ingest import run_ingest
from app.services.obsidian_backfill import backfill_obsidian_exports
from app.services.settings import load_settings

logger = logging.getLogger(__name__)


async def _ingest_loop() -> None:
    while True:
        config = get_app_config()
        await asyncio.sleep(config.ingest_interval_seconds)
        settings = load_settings()
        if not settings.get("background_ingest_enabled", False):
            logger.debug("Background ingest is disabled in settings. Skipping.")
            continue

        if not try_begin_pipeline_job("ingest-background"):
            logger.debug("Pipeline busy — skipping background ingest cycle.")
            continue

        db = SessionLocal()
        try:
            stats = await asyncio.to_thread(run_ingest, db)
            logger.info("Background ingest finished: %s", stats)
        except Exception:
            logger.exception("Background ingest failed")
        finally:
            db.close()
            end_pipeline_job()


def _run_startup_ingest() -> None:
    if not try_begin_pipeline_job("ingest-startup"):
        logger.info("Pipeline busy — skipping startup ingest.")
        return
    db = SessionLocal()
    try:
        stats = run_ingest(db)
        logger.info("Startup ingest finished: %s", stats)
    except Exception:
        logger.exception("Startup ingest failed")
    finally:
        db.close()
        end_pipeline_job()


def _run_hype_backfill() -> None:
    db = SessionLocal()
    try:
        updated = backfill_missing_hype(db)
        if updated:
            logger.info("Hype backfill updated %s items on startup", updated)
    except Exception:
        logger.exception("Startup hype backfill failed")
    finally:
        db.close()


def _run_obsidian_backfill() -> None:
    db = SessionLocal()
    try:
        result = backfill_obsidian_exports(db)
        if result["updated"]:
            logger.info(
                "Obsidian backfill marked %s exported notes on startup",
                result["updated"],
            )
    except Exception:
        logger.exception("Startup Obsidian backfill failed")
    finally:
        db.close()


def _run_migrations() -> None:
    try:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import inspect

        alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        if "news_items" in existing_tables:
            with engine.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
            if current is None:
                command.stamp(alembic_cfg, "head")
                logger.info("Existing SQLite schema detected — stamped Alembic at head")
                return

        command.upgrade(alembic_cfg, "head")
    except Exception:
        logger.exception("Alembic upgrade failed — falling back to create_all + migrate_sqlite_schema")
        Base.metadata.create_all(bind=engine)
        migrate_sqlite_schema()


@asynccontextmanager
async def app_lifespan(app):
    config = get_app_config()
    settings = load_settings()
    logger.info(
        "TechPulse config: allow_seed=%s api_key=%s batch_size=%s background_ingest=%s pipeline_mode=%s",
        config.allow_seed,
        "set" if config.techpulse_api_key else "off",
        config.ingest_batch_size,
        settings.get("background_ingest_enabled"),
        settings.get("pipeline_mode"),
    )
    _run_migrations()

    asyncio.create_task(asyncio.to_thread(_run_hype_backfill))
    asyncio.create_task(asyncio.to_thread(_run_obsidian_backfill))

    if config.ingest_on_startup:
        await asyncio.to_thread(_run_startup_ingest)

    ingest_task = asyncio.create_task(_ingest_loop())

    yield

    ingest_task.cancel()
    try:
        await ingest_task
    except asyncio.CancelledError:
        pass
