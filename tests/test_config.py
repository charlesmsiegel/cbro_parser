"""Tests for cbro_parser.config module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from cbro_parser.config import Config, get_config, reset_config


class TestConfig:
    """Tests for Config class."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_config_loads_api_key(self, temp_env_file):
        """Test that config loads API key from .env file."""
        config = Config(temp_env_file)
        assert config.comicvine_api_key == "test_api_key_12345"

    def test_config_missing_api_key_raises(self, temp_dir, monkeypatch):
        """Test that missing API key raises ValueError."""
        # Clear any existing env var
        monkeypatch.delenv("COMICVINE_API", raising=False)

        empty_env = temp_dir / ".env"
        empty_env.write_text("")

        with pytest.raises(ValueError, match="COMICVINE_API"):
            Config(empty_env)

    def test_config_default_values(self, temp_env_file):
        """Test default configuration values."""
        config = Config(temp_env_file)

        assert config.cv_base_url == "https://comicvine.gamespot.com/api"
        assert config.cv_rate_limit_requests == 200
        assert config.cv_rate_limit_window_seconds == 900
        assert config.cv_safe_delay_seconds == 1.0
        assert config.cbro_base_url == "https://www.comicbookreadingorders.com"
        assert config.cbro_crawl_delay_seconds == 5
        assert config.cache_db_path == Path("comicvine_cache.db")
        assert config.cache_expiry_days == 30
        assert config.default_output_dir == Path("Reading Lists")

    def test_set_cache_path(self, temp_env_file, temp_dir):
        """Test setting custom cache path."""
        config = Config(temp_env_file)
        new_path = temp_dir / "custom_cache.db"

        config.set_cache_path(new_path)

        assert config.cache_db_path == new_path

    def test_set_output_dir(self, temp_env_file, temp_dir):
        """Test setting custom output directory."""
        config = Config(temp_env_file)
        new_dir = temp_dir / "custom_output"

        config.set_output_dir(new_dir)

        assert config.default_output_dir == new_dir


class TestGetConfig:
    """Tests for get_config function."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_get_config_returns_singleton(self, temp_env_file):
        """Test that get_config returns the same instance."""
        config1 = get_config(temp_env_file)
        config2 = get_config()

        assert config1 is config2

    def test_get_config_creates_instance(self, temp_env_file):
        """Test that get_config creates Config instance."""
        config = get_config(temp_env_file)

        assert isinstance(config, Config)
        assert config.comicvine_api_key == "test_api_key_12345"


class TestResetConfig:
    """Tests for reset_config function."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_config()

    def test_reset_clears_singleton(self, temp_env_file):
        """Test that reset_config clears the singleton."""
        # Get first config
        config1 = get_config(temp_env_file)

        # Reset should allow getting a new config instance
        reset_config()

        config2 = get_config(temp_env_file)

        # They should be different instances (new object created)
        assert config1 is not config2

    def test_multiple_get_config_returns_same_instance(self, temp_env_file):
        """Test that multiple calls to get_config return same instance."""
        reset_config()

        config1 = get_config(temp_env_file)
        config2 = get_config()  # No path - should return cached

        assert config1 is config2


class TestConfigEnvironmentVariable:
    """Tests for Config with environment variables."""

    def setup_method(self):
        """Reset config and save original env."""
        reset_config()
        self._original_env = os.environ.get("COMICVINE_API")

    def teardown_method(self):
        """Restore original environment."""
        reset_config()
        if self._original_env:
            os.environ["COMICVINE_API"] = self._original_env
        elif "COMICVINE_API" in os.environ:
            del os.environ["COMICVINE_API"]

    def test_config_from_environment_variable(self, temp_dir):
        """Test config loads from environment variable."""
        os.environ["COMICVINE_API"] = "env_api_key"
        empty_env = temp_dir / ".env"
        empty_env.write_text("")  # Empty .env, should use env var

        config = Config(empty_env)

        assert config.comicvine_api_key == "env_api_key"
