from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Intelligent Media Processing Pipeline"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Defaults to SQLite so deployments without PostgreSQL (e.g. Render free
    # tier, Docker without the postgres service) start cleanly with no error.
    # Set DATABASE_URL to a PostgreSQL URL to opt into PostgreSQL.
    DATABASE_URL: str = "sqlite:///./media_pipeline.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10
    API_V1_STR: str = "/api/v1"

    # Visitor tracking — page visits are persisted with IP, approximate
    # location (best-effort lookup) and access time. Set TRACK_VISITS=False
    # to disable storage entirely, GEO_LOOKUP_ENABLED=False to skip the
    # external ip-api.com lookup (location fields stay null).
    TRACK_VISITS: bool = True
    GEO_LOOKUP_ENABLED: bool = True
    GEO_LOOKUP_URL: str = "http://ip-api.com/json/{ip}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
