import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger("media_pipeline")

db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Only attempt PostgreSQL when it was explicitly configured. If it is
# configured but unreachable (e.g. service down), fall back to SQLite
# instead of crashing the whole app at startup.
if db_url.startswith("postgresql"):
    connect_args["connect_timeout"] = 2
    try:
        engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        with engine.connect() as conn:
            pass
    except Exception as exc:
        logger.warning(
            "postgres_unreachable_falling_back_to_sqlite",
            error=str(exc)[:200],
        )
        db_url = "sqlite:///./media_pipeline.db"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
