"""Configuration management for CBRO Parser."""

import os
import threading
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """Application configuration loaded from environment variables."""

    def __init__(self, env_path: Path | None = None):
        """
        Initialize configuration.

        Args:
            env_path: Optional path to .env file. If not provided,
                      searches in current directory and parent directories.
        """
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        # ComicVine API settings
        self.comicvine_api_key = os.getenv("COMICVINE_API")
        if not self.comicvine_api_key:
            raise ValueError(
                "COMICVINE_API environment variable not set. "
                "Please add it to your .env file."
            )

        self.cv_base_url = "https://comicvine.gamespot.com/api"
        self.cv_rate_limit_requests = 200
        self.cv_rate_limit_window_seconds = 900  # 15 minutes
        self.cv_safe_delay_seconds = 1.0  # 1 request per second is safe

        # CBRO scraper settings
        self.cbro_base_url = "https://www.comicbookreadingorders.com"
        self.cbro_crawl_delay_seconds = 5  # From robots.txt

        # Cache settings
        self.cache_db_path = Path("comicvine_cache.db")
        self.cache_expiry_days = 30

        # Output settings
        self.default_output_dir = Path("Reading Lists")

    def set_cache_path(self, path: Path) -> None:
        """Set the cache database path."""
        self.cache_db_path = path

    def set_output_dir(self, path: Path) -> None:
        """Set the default output directory."""
        self.default_output_dir = path


# Global config instance (lazy loaded) with thread-safe access
_config: Config | None = None
_config_lock = threading.Lock()


def get_config(env_path: Path | None = None) -> Config:
    """
    Get the global configuration instance (thread-safe).

    Args:
        env_path: Optional path to .env file for initialization.

    Returns:
        Config instance.
    """
    global _config
    # Fast path: if already initialized, return without lock
    if _config is not None:
        return _config

    # Slow path: acquire lock and initialize if needed
    with _config_lock:
        # Double-check after acquiring lock (another thread may have initialized)
        if _config is None:
            _config = Config(env_path)
        return _config


def reset_config() -> None:
    """Reset the global configuration (mainly for testing)."""
    global _config
    with _config_lock:
        _config = None
