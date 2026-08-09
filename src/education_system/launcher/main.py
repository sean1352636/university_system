#!/usr/bin/env python3
"""
Education System - Unified Launcher

This module owns ``main()`` and the command-line argument parsing. It is the
single implementation behind all three entry points:

  - ``python -m education_system``     (via education_system/__main__.py)
  - ``education-system``               (console script -> main below)
  - ``python run.py``                  (deprecated root shim)

It delegates the actual work to the sibling education_system.launcher modules:
  - auth:     shared auth init & MFA sync
  - systems:  per-system bootstrap, launchers, dispatch table
  - menus:    CLI interactive mode/system selection
  - roles:    superadmin role-picker dialogs
  - dispatch: GUI/CLI dispatch loops with system-switch handling
"""

import sys
import os
import argparse
import logging
import warnings

# Make the package importable when this file is run as a plain script.
# Insert src/, NOT the education_system package directory itself: the latter
# would put education_system/platform/ on sys.path and shadow the stdlib
# `platform` module. main.py -> launcher -> education_system -> src.
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)

# Load the root .env as early as possible — before any auth bootstrap or
# seeding runs — so flags like EDU_DEV_SEED and EDU_INITIAL_ADMIN_* are in
# os.environ when seed_default_users() first fires. Real environment variables
# still take precedence (load_dotenv does not override existing keys).
try:
    from dotenv import load_dotenv as _load_dotenv

    # main.py -> launcher -> education_system -> src -> repository root.
    # Keep this aligned with README.md and .env.example at the repository root.
    _root_env = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        ),
        ".env",
    )
    if os.path.exists(_root_env):
        _load_dotenv(_root_env)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Startup verbosity. The console stays at WARNING+ by default so launching the
# app isn't buried under INFO chatter (alembic plugin setup, migration notices,
# import banners) — which also spares the terminal-I/O cost of printing it all.
# Everything is still emitted at INFO to any file handler. Pass --verbose/-v
# (or set EDU_VERBOSE=1) to see INFO on the console for debugging.
_VERBOSE_STARTUP = (
    "--verbose" in sys.argv or "-v" in sys.argv or os.environ.get("EDU_VERBOSE") == "1"
)

# Interactive launches default to compact warnings. Operators can opt into
# request/startup detail with --verbose, or retain machine-readable production
# logging by explicitly setting LOG_FORMAT=json and LOG_LEVEL=INFO.
os.environ.setdefault("LOG_FORMAT", "text")
os.environ.setdefault("LOG_LEVEL", "INFO" if _VERBOSE_STARTUP else "WARNING")

# Eventlet is pulled in by the current Socket.IO transport and emits a long
# third-party migration notice on every launch. Keep it out of the normal
# console; it remains visible when Python warnings are explicitly enabled.
warnings.filterwarnings(
    "ignore",
    message=r"\s*Eventlet is deprecated.*",
    category=Warning,
)


def _quiet_console():
    """Raise every console (stderr) handler on the root logger to WARNING
    (unless verbose), leaving file handlers at their level so file logs keep
    full detail.

    Must be re-applied after Alembic runs: alembic's ``fileConfig()`` rebuilds
    the root handlers from ``alembic.ini`` and would otherwise restore an
    INFO-level console for the rest of the session.
    """
    root = logging.getLogger()
    level = logging.INFO if _VERBOSE_STARTUP else logging.WARNING
    if _VERBOSE_STARTUP:
        # alembic's fileConfig pins the root logger at WARNING, which would
        # stop INFO records from ever being created. Lift it so --verbose
        # actually surfaces app INFO on the console.
        root.setLevel(logging.INFO)
    for h in root.handlers:
        # RotatingFileHandler/FileHandler subclass StreamHandler — only touch
        # real console handlers, never the file handler.
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(level)
    if not _VERBOSE_STARTUP:
        for noisy in ("alembic", "alembic.runtime.migration",
                      "sqlalchemy", "sqlalchemy.engine"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


_quiet_console()

SYSTEM_PACKAGE_DIRS = {
    "university": "systems/university",
    "sixth_form": "systems/sixth_form",
    "secondary": "systems/secondary",
    "primary": "systems/primary",
    "nursery": "systems/nursery",
    "apprenticeships": "systems/apprenticeships",
    "fe_college": "systems/fe_college",
}

SYSTEM_DISPLAY_NAMES = {
    "university": "University",
    "sixth_form": "Sixth Form",
    "secondary": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
    "apprenticeships": "Apprenticeships",
    "fe_college": "FE College",
}


# ── Backward-compatible functions expected by tests ──────────────────────────

def log_error(message, error=None):
    """Log an error message. Used by tests; delegates to the module logger."""
    if error:
        logger.error("%s: %s", message, error, exc_info=True)
    else:
        logger.error(message)


def display_interface_menu():
    """Interactive menu that returns 'cli' or 'gui', or exits."""
    while True:
        print()
        print("=" * 54)
        print("       UNIVERSITY MANAGEMENT SYSTEM")
        print("=" * 54)
        print()
        print("  [1] Command Line Interface (CLI)")
        print("  [2] Graphical User Interface (GUI)")
        print("  [3] Run Tests")
        print("  [4] Exit")
        print()
        try:
            choice = input("  Select option: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Exiting...")
            sys.exit(0)

        if choice == "1":
            return "cli"
        elif choice == "2":
            return "gui"
        elif choice == "3":
            try:
                from tests.systems.university._support.run_all_tests import main as run_tests_main
                run_tests_main()
            except Exception:
                pass
            sys.exit(0)
        elif choice == "4":
            print("  Goodbye!")
            sys.exit(0)
        else:
            print("  Invalid choice. Please try again.")


def run_cli_mode():
    """Launch CLI mode with error handling. Returns True on success, False on failure."""
    print("  Starting Command Line Interface...")
    try:
        from education_system.systems.university.interfaces.cli.shell.cli_main import main as cli_main
        cli_main()
        return True
    except ImportError as e:
        print(f"  CLI Import Error: {e}")
        log_error("CLI import error", e)
        return False
    except OSError as e:
        print(f"  CLI Application Error: {e}")
        log_error("CLI OS error", e)
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}")
        log_error("CLI unexpected error", e)
        return False


def run_gui_mode():
    """Launch GUI mode with error handling and CLI fallback. Returns True on success."""
    print("  Starting Graphical User Interface...")
    try:
        from education_system.systems.university.interfaces.gui.shell.gui_launcher import launch_main_gui
        launch_main_gui()
        return True
    except ImportError as e:
        print(f"  GUI Import Error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI import error", e)
        return run_cli_mode()
    except OSError as e:
        print(f"  GUI Application Error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI OS error", e)
        return run_cli_mode()
    except Exception as e:
        print(f"  Unexpected error: {e}")
        print("  Falling back to CLI mode...")
        log_error("GUI unexpected error", e)
        return run_cli_mode()


def _api_is_running(host: str = "localhost", port: int = 5000) -> bool:
    """Quick TCP check — is the unified API already listening?"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _start_api_in_background(port: int = 5000, cors_origins: str | None = None):
    """Spawn the unified API server in a daemon thread.

    The login page fetches /api/v1/auth/login from this server. Having --web
    launch it automatically means the user only needs one command.

    ``cors_origins`` is a comma-separated allow-list of the exact origins the
    static web server is served from (e.g. ``http://localhost:8000``). We never
    fall back to a wildcard — the unified server refuses to start with ``*`` and
    a wildcard here would let any site on the machine call the authenticated API.
    """
    import threading
    if cors_origins:
        os.environ.setdefault("API_CORS_ORIGINS", cors_origins)
    os.environ.setdefault("API_PORT", str(port))

    def _runner():
        try:
            from education_system.platform.delivery.api.unified_server import run_unified_api
            run_unified_api(port=port)
        except Exception as exc:
            logger.error("Unified API server crashed: %s", exc, exc_info=True)

    t = threading.Thread(target=_runner, name="unified-api", daemon=True)
    t.start()
    return t


def run_web_server(system="university", port=8000, open_browser=True,
                   api_port: int = 5000, start_api: bool = True):
    """Serve the system static HTML UI over HTTP and open a browser.

    Using a real HTTP server avoids the file:// security restrictions
    (cross-origin file links, blocked downloads, etc.).

    The login page talks to the unified Flask API (/api/v1/auth/*) for real
    authentication against auth.db. If that API isn't already running on
    ``api_port``, this function starts it in a background thread so the
    single --web flag gives you a working login out of the box.
    """
    import http.server
    import socketserver
    import webbrowser
    from functools import partial
    from pathlib import Path

    # main.py -> launcher -> education_system (the package root).
    package_root = Path(__file__).resolve().parents[1]
    package_dir = SYSTEM_PACKAGE_DIRS.get(system, f"{system}_system")
    web_dir = package_root / package_dir / "assets" / "web"

    if not web_dir.is_dir():
        print(f"  ✗ Web directory not found: {web_dir}")
        sys.exit(1)

    # Serve ONLY this system's static web directory. Serving the repository
    # root exposed every tracked file over HTTP — including the raw auth.db,
    # audit.db and student_records.db — to anyone who could reach the port.
    # The web pages talk to the API via an absolute URL and only link to each
    # other, so the web/ directory is self-contained.
    serve_root = web_dir
    # Start at the public welcome page. Authentication is an explicit user
    # action from there rather than the first screen shown at launch.
    url = f"http://localhost:{port}/university.html"

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(serve_root))

    # ── Auto-start the unified API if it isn't already running ─────────
    # Restrict CORS to the exact origin this static server is served from.
    web_origins = f"http://localhost:{port},http://127.0.0.1:{port}"
    api_url = f"http://localhost:{api_port}/api/v1/auth/login"
    api_status = "already running"
    if start_api and not _api_is_running(port=api_port):
        _start_api_in_background(port=api_port, cors_origins=web_origins)
        # Importing the unified application can take several seconds. Do not
        # open the login page until its API is actually accepting connections.
        import time
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not _api_is_running(port=api_port):
            time.sleep(0.25)
        api_status = "running" if _api_is_running(port=api_port) else "still starting"

    print()
    print("  " + "=" * 56)
    system_name = SYSTEM_DISPLAY_NAMES.get(system, system.title())
    print(f"   {system_name} System — Web UI")
    print("  " + "=" * 56)
    print(f"  Serving:  {serve_root}")
    print(f"  URL:      {url}")
    print(f"  Auth API: {api_url}  ({api_status})")
    print(f"  Press Ctrl+C to stop the server.")
    print()

    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            if open_browser:
                try:
                    webbrowser.open(url)
                except Exception as exc:
                    logger.debug("Could not auto-open browser: %s", exc)
            httpd.serve_forever()
    except OSError as exc:
        print(f"  ✗ Could not start server on port {port}: {exc}")
        print(f"    Try a different port: python run.py --web --web-port 8080")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Server stopped.")


# ── Main entry ────────────────────────────────────────────────────────────────

def _apply_quiet_mode():
    """Configure env before any education_system imports so startup is quiet.

    Must run before the unified server's setup_structured_logging is called,
    otherwise its _configured sentinel locks in the default INFO/JSON output.
    """
    if "--quiet" not in sys.argv and "-q" not in sys.argv:
        return
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    os.environ.setdefault("LOG_FORMAT", "text")
    # Quiet mode only affects logging verbosity — it must never relax CORS.
    # (The unified server fails closed on a wildcard origin.)
    # Override the INFO level set by logging.basicConfig at module import.
    logging.getLogger().setLevel(logging.WARNING)


def _run_alembic_upgrade():
    """Apply pending Alembic migrations to student_records.db at startup.

    Failure handling distinguishes two cases:

    * **Alembic unavailable / not configured** (ImportError) — non-fatal. Alembic
      is optional tooling; a genuine schema failure is something else.
    * **A real migration failure** (``command.upgrade`` raises) — treated as an
      *essential* failure and aborts startup, because continuing would run the
      application against a schema that is behind or inconsistent with the code,
      risking data corruption. Set ``EDU_ALLOW_SCHEMA_DRIFT=1`` to downgrade this
      to a warning — e.g. when launching a non-university system (the migrations
      only cover the university ``student_records.db``) or when intentionally
      working against an older schema in development.
    """
    try:
        from alembic.config import Config
        from alembic import command
    except ImportError as e:
        logger.warning("Alembic not available — skipping migrations: %s", e)
        return

    # alembic.ini lives in education_system/ (8.117.84 moved it there so the
    # project is self-contained). The config's relative sqlalchemy.url and
    # script_location resolve against the directory that holds alembic.ini, so we
    # also chdir there for the upgrade.
    # alembic.ini sits in the education_system package directory:
    # main.py -> launcher -> education_system.
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(project_dir, "alembic.ini")
    prev_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cfg = Config(ini_path)
        command.upgrade(cfg, "head")
    except Exception as e:
        allow_drift = os.environ.get("EDU_ALLOW_SCHEMA_DRIFT", "").strip().lower() in (
            "1", "true", "yes", "on",
        )
        if allow_drift:
            logger.warning(
                "Alembic upgrade failed but EDU_ALLOW_SCHEMA_DRIFT is set — "
                "continuing against a possibly-inconsistent schema: %s", e,
            )
        else:
            logger.error(
                "Alembic upgrade to head failed: %s. Refusing to start against a "
                "possibly-inconsistent schema. Fix the migration, or set "
                "EDU_ALLOW_SCHEMA_DRIFT=1 to override (e.g. when launching a "
                "non-university system).", e,
            )
            raise SystemExit(1) from e
    finally:
        os.chdir(prev_cwd)


def _seed_demo_if_fresh():
    """Re-seed demo student S12345's modules when the DB has been rebuilt.

    Triggers when S12345 has zero enrolments (i.e. the DB was deleted
    and just regenerated from migrations, which only seed the catalog).
    Idempotent: re-running is a no-op once enrolments are in place.
    """
    try:
        import sqlite3
        db = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "var/data/university/db_files/student_records.db",
        )
        if not os.path.exists(db):
            return
        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM student_modules WHERE student_id = 'S12345'"
        ).fetchone()[0]
        if n > 0:
            conn.close()
            return
        conn.execute(
            "INSERT OR IGNORE INTO students (student_id, first_name, last_name) "
            "VALUES ('S12345', 'Demo', 'Student')"
        )
        from tools.university.seed_demo_data import (
            seed_s12345_modules,
        )
        cur = conn.cursor()
        seed_s12345_modules(cur)
        conn.commit()
        conn.close()
        logger.info("Re-seeded demo modules for S12345 (fresh DB detected).")
    except Exception as e:
        logger.warning("Demo re-seed skipped: %s", e)


def main():
    _apply_quiet_mode()
    _run_alembic_upgrade()
    _quiet_console()  # alembic's fileConfig reset the root console handler
    _seed_demo_if_fresh()

    # Windows across the tree hardcode sizes drawn on a desktop monitor —
    # 1400x900 with a 1200x800 floor is the house convention. On a smaller
    # display that opens taller than the screen and the minsize stops the
    # user shrinking it, so whatever is packed last (usually the action
    # buttons) is unreachable. Clamping here covers every window, including
    # the login dialog shown before a system is chosen.
    try:
        from education_system.platform.delivery.gui.window_sizing import install
        install()
    except Exception as exc:
        logger.debug("window sizing not installed: %s", exc)

    # Bootstrap cross-domain bus schemas + eagerly import every bus
    # module so self-registering subscribers (email_bus,
    # student_union_bus calendar publisher, etc.) wire up before the
    # first user action triggers them. Best-effort — failures are
    # logged at debug; the launcher continues.
    try:
        from education_system.systems.university.services.bus import (
            bus_migrations,
        )
        bus_migrations.ensure_all_bus_schemas()
        bus_migrations.bootstrap_all_bus_subscribers()
    except Exception as exc:
        logger.debug("bus bootstrap skipped: %s", exc)

    from education_system.launcher.auth import gui_universal_login, cli_universal_login
    from education_system.launcher.systems import (
        LAUNCHERS, AUTH_GUI_SYSTEMS, AUTH_CLI_SYSTEMS,
        run_unified_api, run_all_system_tests, run_seed,
    )
    from education_system.launcher.menus import cli_select_mode, cli_select_system
    from education_system.launcher.dispatch import dispatch_gui, dispatch_cli

    parser = argparse.ArgumentParser(
        description="Education System Launcher",
        epilog="If no flags are given an interactive menu is shown.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--cli", action="store_true", help="Command-line interface")
    mode_group.add_argument("--gui", action="store_true", help="Graphical interface")
    mode_group.add_argument("--api", action="store_true", help="REST API server")
    mode_group.add_argument("--web", action="store_true", help="Open the static HTML web UI in a browser")
    mode_group.add_argument("--test", action="store_true", help="Run test suite")
    mode_group.add_argument("--test-all", action="store_true", help="Run tests for all systems")

    parser.add_argument("--web-port", type=int, default=8000, help="Port for --web mode (default: 8000)")
    parser.add_argument("--web-no-browser", action="store_true", help="Don't auto-open browser in --web mode")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress INFO startup logs (WARNING+ only, human-readable text format)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show INFO-level startup logs on the console (default is WARNING+)")

    parser.add_argument("--seed", type=int, metavar="N", help="Seed database with N demo students")

    sys_group = parser.add_mutually_exclusive_group()
    sys_group.add_argument("--university", action="store_true", help="University system")
    sys_group.add_argument("--college", "--sixthform", action="store_true",
                           dest="college", help="Sixth Form College system")
    sys_group.add_argument("--secondary", "--school", action="store_true",
                           dest="secondary", help="Secondary School system")
    sys_group.add_argument("--primary", action="store_true", help="Primary School system")
    sys_group.add_argument("--nursery", action="store_true",
                           help="Nursery / Early Years system")
    sys_group.add_argument("--apprenticeships", "--apprenticeship", action="store_true",
                           dest="apprenticeships", help="Apprenticeships system")
    sys_group.add_argument("--fecollege", "--fe-college", action="store_true",
                           dest="fecollege", help="FE College system")

    args = parser.parse_args()

    # Resolve mode from flags
    mode = None
    if args.cli:
        mode = "cli"
    elif args.gui:
        mode = "gui"
    elif args.api:
        mode = "api"
    elif args.web:
        mode = "web"
    elif args.test:
        mode = "test"
    elif args.test_all:
        mode = "test-all"

    # Resolve system from flags. These keys are the canonical auth/launcher
    # identifiers; filesystem package names are mapped separately.
    if args.university:
        system = "university"
    elif args.college:
        system = "sixth_form"
    elif args.secondary:
        system = "secondary"
    elif args.primary:
        system = "primary"
    elif args.nursery:
        system = "nursery"
    elif args.apprenticeships:
        system = "apprenticeships"
    elif args.fecollege:
        system = "fe_college"
    else:
        system = None

    # ── Web mode ───────────────────────────────────────────────────────
    if mode == "web":
        run_web_server(
            system=system or "university",
            port=args.web_port,
            open_browser=not args.web_no_browser,
        )
        return

    # ── Seed mode ──────────────────────────────────────────────────────
    if args.seed:
        if system is None:
            system = cli_select_system()
            if system is None:
                return
        run_seed(system, args.seed)
        return

    # ── Test-all mode ──────────────────────────────────────────────────
    if mode == "test-all":
        success = run_all_system_tests()
        sys.exit(0 if success else 1)

    # ── Unified i18n setup ─────────────────────────────────────────────
    try:
        from education_system.platform.features.i18n import init_i18n

        if mode == "gui" or mode is None:
            from education_system.platform.features.i18n.selector_gui import show_language_selector
            chosen = show_language_selector()
            init_i18n(chosen)
        elif mode == "cli":
            from education_system.platform.features.i18n.selector_cli import show_language_selector_cli
            chosen = show_language_selector_cli()
            init_i18n(chosen)
        else:
            init_i18n()
    except Exception as exc:
        logger.debug("i18n init skipped: %s", exc)

    # Interactive fallbacks
    if mode is None:
        mode = cli_select_mode()
        if mode is None:
            return

    if mode == "web":
        if system is None:
            system = cli_select_system()
            if system is None:
                return
        run_web_server(system=system, port=args.web_port, open_browser=not args.web_no_browser)
        return

    if mode == "test-all":
        success = run_all_system_tests()
        sys.exit(0 if success else 1)

    # ── Direct authenticated launch ─────────────────────────────────────
    if mode == "gui" and system in AUTH_GUI_SYSTEMS:
        result = gui_universal_login(target_system=system)
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_gui(user_info, system, role, shared_auth)
        return

    if mode == "cli" and system in AUTH_CLI_SYSTEMS:
        result = cli_universal_login(target_system=system)
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_cli(user_info, system, role, shared_auth)
        return

    # ── GUI with universal login ───────────────────────────────────────
    if mode == "gui" and system is None:
        result = gui_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_gui(user_info, system, role, shared_auth)
        return

    # ── CLI with universal login ───────────────────────────────────────
    if mode == "cli" and system is None:
        result = cli_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result
        dispatch_cli(user_info, system, role, shared_auth)
        return

    # ── API mode ───────────────────────────────────────────────────────
    if mode == "api":
        run_unified_api()
        return

    # ── Direct system launch (system already specified) ────────────────
    while system is None:
        system = cli_select_system()
        if system is None:
            mode = cli_select_mode()
            if mode is None:
                return
            if mode == "test-all":
                success = run_all_system_tests()
                sys.exit(0 if success else 1)
            continue

    # Set the active-system display name so shared surfaces (MFA
    # email subject/body, log lines, window titles) identify *this*
    # system rather than whatever the default was at import time.
    try:
        from education_system.platform import branding
        from education_system.launcher.roles import SYSTEM_NAMES
        if system in SYSTEM_NAMES:
            branding.set_system_name(SYSTEM_NAMES[system])
    except Exception:
        pass

    while True:
        launcher = LAUNCHERS.get((system, mode))
        if launcher is None:
            print(f"  Unknown combination: {system} + {mode}")
            sys.exit(1)

        try:
            launcher()
        except KeyboardInterrupt:
            print("\n\n  Interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)
            print(f"\n  Error: {e}")
            sys.exit(1)

        from education_system.switch import consume
        switch_request = consume()
        if switch_request is None:
            break
        system, mode = switch_request

        # A logout from any per-system launcher schedules ("__login__", mode);
        # bounce through the universal login and then hand off to the full
        # auth-aware dispatch loop so subsequent switches keep working.
        if system == "__login__":
            print("\n  Returning to login...\n")
            if mode == "gui":
                result = gui_universal_login()
                if result is None:
                    return
                user_info, system, role, shared_auth = result
                dispatch_gui(user_info, system, role, shared_auth)
                return
            if mode == "cli":
                result = cli_universal_login()
                if result is None:
                    return
                user_info, system, role, shared_auth = result
                dispatch_cli(user_info, system, role, shared_auth)
                return
            print(f"  Cannot return to login in mode '{mode}'")
            sys.exit(1)

        print(f"\n  Switching to {system} ({mode})...\n")


if __name__ == "__main__":
    main()
