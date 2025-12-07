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


class TestConfigThreadSafety:
    """Tests for thread-safe config access.

    Regression tests for: Global Config Not Thread-Safe bug
    - config.py:72,80 uses global variable pattern without thread safety
    - GUI uses multiple threads (app.py:339,418)
    """

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_concurrent_get_config_returns_same_instance(self, temp_env_file):
        """Test that concurrent get_config calls return the same instance.

        Without thread safety, multiple threads could each create their own
        Config instance when they all see _config as None simultaneously.
        """
        import threading
        import time

        results = []
        errors = []
        num_threads = 10
        barrier = threading.Barrier(num_threads)

        def get_config_thread():
            try:
                # Wait for all threads to be ready
                barrier.wait()
                # All threads call get_config at the same time
                config = get_config(temp_env_file)
                results.append(config)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=get_config_thread)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"
        assert len(results) == num_threads

        # All threads should have gotten the exact same Config instance
        first_config = results[0]
        for i, config in enumerate(results[1:], 2):
            assert config is first_config, (
                f"Thread {i} got a different Config instance! "
                "This indicates a race condition in get_config()."
            )

    def test_concurrent_get_config_only_creates_one_instance(self, temp_env_file):
        """Test that concurrent access only creates one Config instance.

        This test patches Config.__init__ to count instantiations.
        Without thread safety, multiple instances could be created.
        """
        import threading
        from unittest.mock import patch

        instantiation_count = 0
        original_init = Config.__init__

        def counting_init(self, env_path=None):
            nonlocal instantiation_count
            instantiation_count += 1
            # Small delay to increase chance of race condition
            import time
            time.sleep(0.01)
            return original_init(self, env_path)

        num_threads = 10
        barrier = threading.Barrier(num_threads)
        results = []

        def get_config_thread():
            barrier.wait()
            config = get_config(temp_env_file)
            results.append(config)

        with patch.object(Config, '__init__', counting_init):
            threads = [
                threading.Thread(target=get_config_thread)
                for _ in range(num_threads)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # Should only create ONE instance, not multiple
        assert instantiation_count == 1, (
            f"Config was instantiated {instantiation_count} times! "
            "Expected exactly 1. This indicates a race condition."
        )

    def test_reset_config_thread_safety(self, temp_env_file):
        """Test that reset_config is thread-safe with concurrent get_config.

        One thread resets while others are getting - should not cause errors.
        """
        import threading

        errors = []
        num_getter_threads = 5
        num_iterations = 20

        def getter_thread():
            for _ in range(num_iterations):
                try:
                    config = get_config(temp_env_file)
                    # Access an attribute to ensure config is valid
                    _ = config.comicvine_api_key
                except Exception as e:
                    errors.append(e)

        def resetter_thread():
            for _ in range(num_iterations):
                try:
                    reset_config()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=getter_thread)
            for _ in range(num_getter_threads)
        ]
        threads.append(threading.Thread(target=resetter_thread))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert not errors, f"Thread safety errors: {errors}"


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
