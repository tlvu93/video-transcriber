import logging

from api.config import DATABASE_URL, DB_PATH, IS_POSTGRES
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("database")


ENGINE_KWARGS = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    ENGINE_KWARGS["connect_args"] = {"check_same_thread": False}

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, **ENGINE_KWARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
LEGACY_BASELINE_REVISION = "20250311_legacy_schema"
LEGACY_TABLES = {
    "videos",
    "transcripts",
    "summaries",
    "transcription_jobs",
    "summarization_jobs",
    "translated_transcripts",
    "translation_jobs",
}


def _load_alembic_config() -> Config:
    config = Config("/app/alembic.ini" if DATABASE_URL.startswith("postgresql") else "alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def init_db():
    """Initialize the database."""

    if not IS_POSTGRES:
        logger.warning(
            "Running with SQLite at %s. SQLite is supported for local development only and is not safe for "
            "multi-worker queue leasing.",
            DB_PATH,
        )

    alembic_config = _load_alembic_config()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "alembic_version" not in existing_tables and LEGACY_TABLES.intersection(existing_tables):
        logger.info("Detected pre-Alembic schema, stamping baseline revision %s", LEGACY_BASELINE_REVISION)
        command.stamp(alembic_config, LEGACY_BASELINE_REVISION)

    logger.info("Running database migrations")
    command.upgrade(alembic_config, "head")
    from api.models import TranscriptSegmentSearch
    from api.search_index import rebuild_all_transcript_search_rows

    with SessionLocal() as db:
        if db.query(TranscriptSegmentSearch).count() == 0:
            rebuild_all_transcript_search_rows(db)
    logger.info("Database migrations applied successfully")


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
