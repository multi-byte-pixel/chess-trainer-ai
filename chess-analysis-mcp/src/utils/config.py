"""Configuration management using pydantic-settings."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    lichess_token: str = Field(default="", description="Lichess API token")
    stockfish_path: str = Field(default="/usr/games/stockfish", description="Path to Stockfish binary")
    database_url: str = Field(
        default="postgresql://chess:chess@localhost:5432/chess_analysis",
        description="PostgreSQL connection URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    mcp_host: str = Field(default="0.0.0.0", description="MCP server host")
    mcp_port: int = Field(default=9000, description="MCP server port")
    log_level: str = Field(default="INFO", description="Logging level")
    stockfish_threads: int = Field(default=1, description="Stockfish thread count")
    stockfish_hash_mb: int = Field(default=128, description="Stockfish hash size in MB")
    cloud_eval_cache_ttl: int = Field(default=86400, description="Cloud eval cache TTL in seconds")
    games_cache_ttl: int = Field(default=3600, description="Games cache TTL in seconds")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
