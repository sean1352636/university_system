"""Allow running with: python -m education_system.secondary_school

Usage:
    python -m education_system.secondary_school          # GUI (default)
    python -m education_system.secondary_school --cli     # CLI
    python -m education_system.secondary_school --api     # REST API server
"""

import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gui"

    if mode == "--cli":
        from education_system.secondary_school.cli.cli_main import main as cli_main
        cli_main()
    elif mode == "--api":
        from education_system.shared.api.secondary.api_server import run_server
        run_server()
    else:
        from education_system.secondary_school.main_gui import run
        run()


if __name__ == "__main__":
    main()
