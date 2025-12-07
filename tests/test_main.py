"""Tests for cbro_parser.main module."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestMainModule:
    """Tests for main entry point."""

    @patch("cbro_parser.cli.main")
    def test_main_cli_flag(self, mock_cli, monkeypatch):
        """Test that --cli flag runs CLI mode."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "--cli"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.cli.main")
    def test_main_with_parse_command(self, mock_cli, monkeypatch):
        """Test that parse command runs CLI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "parse", "url"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.cli.main")
    def test_main_with_stats_command(self, mock_cli, monkeypatch):
        """Test that stats command runs CLI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "stats"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.cli.main")
    def test_main_with_batch_command(self, mock_cli, monkeypatch):
        """Test that batch command runs CLI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "batch", "file.txt"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.cli.main")
    def test_main_with_prepopulate_command(self, mock_cli, monkeypatch):
        """Test that prepopulate command runs CLI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "prepopulate", "/path"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.cli.main")
    def test_main_with_help_flag(self, mock_cli, monkeypatch):
        """Test that --help runs CLI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser", "--help"])

        from cbro_parser.main import main

        main()

        mock_cli.assert_called_once()

    @patch("cbro_parser.gui.app.run_app")
    def test_main_default_runs_gui(self, mock_gui, monkeypatch):
        """Test that no args runs GUI."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser"])

        from cbro_parser.main import main

        main()

        mock_gui.assert_called_once()
