"""Main entry point for CBRO Parser."""

import sys


def main() -> None:
    """
    Main entry point.

    Launches GUI by default, or CLI if --cli flag is provided.
    """
    # Check for CLI mode
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from .cli import main as cli_main

        cli_main()
    elif len(sys.argv) > 1 and sys.argv[1] in (
        "parse",
        "batch",
        "prepopulate",
        "stats",
        "-h",
        "--help",
    ):
        # CLI commands were provided
        from .cli import main as cli_main

        cli_main()
    else:
        # Default to GUI
        from .gui.app import run_app

        run_app()


if __name__ == "__main__":
    main()
