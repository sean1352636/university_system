"""Entry point for the Primary School Management System.

Usage:
    python -m education_system.primary_school          # GUI (default)
    python -m education_system.primary_school --cli     # CLI mode
    python -m education_system.primary_school --api     # API mode
"""

import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gui"

    if mode == "--gui":
        from education_system.primary_school.main_gui import run
        run()
    elif mode == "--cli":
        from education_system.primary_school.cli.cli_main import main as cli_main
        cli_main()
    elif mode == "--api":
        from education_system.shared.api.primary.api_server import run_server
        run_server()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python -m education_system.primary_school [--gui|--cli|--api]")
        sys.exit(1)


if __name__ == "__main__":
    main()
