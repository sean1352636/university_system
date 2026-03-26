#!/usr/bin/env python3
"""
Education System - Unified Launcher
Entry point with universal authentication and system selection.
"""

import sys
import os
import argparse
import logging
import subprocess

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── Shared auth initialisation ───────────────────────────────────────────────

def _init_shared_auth():
    """Initialise the shared auth database on first run."""
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    initialise_auth_db()
    seed_default_users()


def _sync_university_mfa_to_shared():
    """Copy any TOTP secrets from the university DB to the shared auth DB.

    This ensures that users who set up MFA through the university GUI
    before the shared-auth sync was added will still be prompted for
    TOTP when logging in via the universal login.
    """
    import sqlite3

    # Read TOTP secrets from university DB
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
    uni_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    uni_conn.row_factory = sqlite3.Row
    try:
        rows = uni_conn.execute(
            "SELECT ua.user_id, ua.username, ua.two_fa_secret "
            "FROM user_accounts ua "
            "WHERE ua.two_fa_secret IS NOT NULL AND ua.two_fa_secret != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return  # table or column doesn't exist yet
    finally:
        uni_conn.close()

    if not rows:
        return

    # Write them to the shared auth mfa_secrets table
    from education_system.shared.auth.db import connect as shared_connect
    shared_conn = shared_connect()
    try:
        synced = 0
        for row in rows:
            username = row["username"]
            secret = row["two_fa_secret"]

            # Look up the shared-auth user ID by username
            shared_row = shared_conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not shared_row:
                continue

            shared_uid = shared_row["id"]

            # Only insert if not already present
            existing = shared_conn.execute(
                "SELECT id FROM mfa_secrets WHERE user_id = ?", (shared_uid,)
            ).fetchone()
            if existing:
                continue

            shared_conn.execute(
                "INSERT INTO mfa_secrets (user_id, totp_secret, is_enabled) "
                "VALUES (?, ?, 1)",
                (shared_uid, secret),
            )
            synced += 1

        if synced:
            shared_conn.commit()
            logger.info("Synced %d university TOTP secret(s) to shared auth DB", synced)
    finally:
        shared_conn.close()


# ── Universal GUI login ─────────────────────────────────────────────────────

def gui_universal_login() -> tuple[dict, str, str, object] | None:
    """Show the universal login window.

    Returns (user_info, system_key, system_role, auth) or None if cancelled.
    """
    _init_shared_auth()

    from education_system.shared.gui.login_gui import UniversalLoginWindow
    login = UniversalLoginWindow()
    login.mainloop()

    if login.user_info and login.system_key:
        return login.user_info, login.system_key, login.system_role, login.auth
    return None


# ── Universal CLI login ─────────────────────────────────────────────────────

def cli_universal_login() -> tuple[dict, str, str, object] | None:
    """Show the universal CLI login prompt.

    Returns (user_info, system_key, system_role, auth) or None if cancelled.
    """
    _init_shared_auth()

    from education_system.shared.cli.login_cli import universal_cli_login
    return universal_cli_login()


# ── University System launchers ───────────────────────────────────────────────

def _init_university():
    """One-time university system bootstrap (env, i18n, auth, DB)."""
    # Ensure shared auth is ready before university auth init
    _init_shared_auth()

    try:
        from dotenv import load_dotenv
        env = os.path.join(os.path.dirname(__file__),
                           "education_system", "university_system", ".env")
        if os.path.exists(env):
            load_dotenv(env)
    except ImportError:
        pass

    from education_system.university_system.modules.shared.constants.paths import ensure_directories
    ensure_directories()

    from education_system.university_system.modules.shared.utils.i18n import init_i18n
    # Use shared i18n language choice (already selected at startup)
    try:
        from education_system.shared.i18n import get_current_language
        init_i18n(get_current_language())
    except Exception:
        init_i18n("en")

    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import set_auth
    set_auth(UserAuth())

    from education_system.university_system.core.defaults import print_generated_passwords
    print_generated_passwords()

    from education_system.university_system.infrastructure.database.database_utils import init_db
    init_db()

    # Migrate existing university accounts to shared auth DB
    try:
        from education_system.university_system.infrastructure.auth.migration_to_shared import migrate
        migrate()
    except Exception as exc:
        logger.debug("University auth migration skipped: %s", exc)

    # Sync any existing university TOTP secrets to the shared auth DB so
    # the universal login can enforce MFA for users who set it up before
    # the shared-auth MFA sync was added.
    try:
        _sync_university_mfa_to_shared()
    except Exception as exc:
        logger.debug("University MFA sync skipped: %s", exc)


def run_university_cli(user_info=None, role=None, shared_auth=None):
    _init_university()
    from education_system.university_system.modules.shared.utils.i18n import init_i18n, get_text as _
    # Use language already chosen via the shared i18n selector at startup
    try:
        from education_system.shared.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_cli"))
    from education_system.university_system.modules.shared.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_university_gui(user_info=None, role=None, shared_auth=None):
    _init_university()
    from education_system.university_system.modules.shared.utils.i18n import init_i18n, get_text as _
    # Use language already chosen via the shared i18n selector at startup
    try:
        from education_system.shared.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_gui"))

    if not user_info or not shared_auth:
        # No pre-auth — show universal login first
        result = gui_universal_login()
        if result is None:
            return
        user_info, _sys, role, shared_auth = result

    # Build a session_user dict in the university format
    uni_role = role or "student"
    for s in user_info.get("systems", []):
        if s["system_key"] == "university":
            uni_role = s["role"]
            break
    # Load permissions for the role from the university auth constants
    from education_system.university_system.infrastructure.auth.core_utils.constants import PERMISSIONS
    uni_permissions = list(PERMISSIONS.get(uni_role, []))

    # Look up the legacy user ID from the university DB so that existing
    # database references (messages, grades, etc.) still match.
    legacy_user_id = None
    student_id = None
    try:
        from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(str(DEFAULT_DB_PATH))
        _row = _conn.execute(
            "SELECT id, student_id FROM users WHERE username = ?",
            (user_info["username"],)
        ).fetchone()
        if _row:
            legacy_user_id = _row[0]
            student_id = _row[1]
        _conn.close()
    except Exception:
        pass

    effective_id = legacy_user_id or user_info["user_id"]

    session_user = {
        "id": effective_id,
        "user_id": effective_id,
        "shared_auth_id": user_info["user_id"],
        "username": user_info["username"],
        "display_name": user_info.get("display_name", user_info["username"]),
        "role": uni_role,
        "permissions": uni_permissions,
        "password_reset_required": 0,
        "student_id": student_id,
        "email": user_info.get("email", ""),
        "systems": user_info.get("systems", []),
    }
    from education_system.university_system.modules.shared.gui.main.main_gui import init_gui
    app = init_gui(session_user=session_user)
    app.run()


def run_unified_api():
    from education_system.shared.api.unified_server import run_unified_api
    run_unified_api()


def run_university_tests():
    from education_system.university_system.tests.run_all_tests import run_all_tests
    return run_all_tests()


def run_all_system_tests():
    """Run tests across all four systems in a single pytest invocation."""
    test_dirs = [
        "education_system/university_system/tests/",
        "education_system/college_system/tests/",
        "education_system/secondary_school/tests/",
        "education_system/primary_school/tests/",
    ]

    print()
    print("=" * 60)
    print("  RUNNING TESTS ACROSS ALL SYSTEMS")
    print("=" * 60)
    print()

    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + test_dirs + [
            "-v", "--tb=short", "-ra", "--color=yes",
        ],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.returncode == 0


# ── College System launchers ──────────────────────────────────────────────────

def _init_college_i18n():
    """Sync college i18n with the shared language choice."""
    try:
        from education_system.shared.i18n import get_current_language
        from education_system.college_system.core.i18n import init_i18n
        init_i18n(get_current_language())
    except Exception:
        pass


def run_college_cli(user_info=None, role=None, shared_auth=None):
    _init_college_i18n()
    from education_system.college_system.modules.shared.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_college_gui(user_info=None, role=None, shared_auth=None):
    _init_college_i18n()
    from education_system.college_system.modules.shared.gui.main_gui import launch_gui
    launch_gui(user_info=user_info, role=role, shared_auth=shared_auth)


def run_college_api():
    run_unified_api()


def run_college_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "education_system/college_system/tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.returncode == 0


# ── School System launchers ──────────────────────────────────────────────────

def run_school_cli(user_info=None, role=None, shared_auth=None):
    from education_system.secondary_school.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_school_gui(user_info=None, role=None, shared_auth=None):
    from education_system.secondary_school.main_gui import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_school_api():
    run_unified_api()


def run_school_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "education_system/secondary_school/tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.returncode == 0


# ── Primary School System launchers ──────────────────────────────────────────

def run_primary_cli(user_info=None, role=None, shared_auth=None):
    from education_system.primary_school.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primary_gui(user_info=None, role=None, shared_auth=None):
    from education_system.primary_school.main_gui import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primary_api():
    run_unified_api()


def run_primary_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "education_system/primary_school/tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.returncode == 0



# ── Seed command (Improvement #19) ────────────────────────────────────────────

def run_seed(system: str, count: int):
    """Seed a system with demo data and export as portable files."""
    from education_system.shared.seeding import DemoSeeder
    from education_system.shared.transfer.portability import StudentDataExporter
    from pathlib import Path

    seeder = DemoSeeder(system_key=system)
    students = seeder.generate_students(count)
    courses = seeder.generate_courses()
    enrollments = seeder.generate_enrollments(students, courses)
    attendance = seeder.generate_attendance(students, days=20)
    grades = seeder.generate_grades(students, courses)

    print(f"\n  Demo Data Generated for {system}:")
    print(f"  {'='*40}")
    print(f"  Students:    {len(students)}")
    print(f"  Courses:     {len(courses)}")
    print(f"  Enrollments: {len(enrollments)}")
    print(f"  Attendance:  {len(attendance)}")
    print(f"  Grades:      {len(grades)}")

    seed_dir = Path(__file__).parent / "education_system" / "shared" / "data" / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)

    exporter = StudentDataExporter(system_name=system.title(), system_key=system)
    exporter.save(seed_dir / f"{system}_students.json", students)
    exporter.save(seed_dir / f"{system}_students.csv", students)
    print(f"\n  Saved to: {seed_dir}/")
    print()


# ── Dispatch table ────────────────────────────────────────────────────────────

LAUNCHERS = {
    ("university", "cli"):    run_university_cli,
    ("university", "gui"):    run_university_gui,
    ("university", "api"):    run_unified_api,
    ("university", "test"):   run_university_tests,
    ("college", "cli"):       run_college_cli,
    ("college", "gui"):       run_college_gui,
    ("college", "api"):       run_college_api,
    ("college", "test"):      run_college_tests,
    ("school", "cli"):        run_school_cli,
    ("school", "gui"):        run_school_gui,
    ("school", "api"):        run_school_api,
    ("school", "test"):       run_school_tests,
    ("primary", "cli"):       run_primary_cli,
    ("primary", "gui"):       run_primary_gui,
    ("primary", "api"):       run_primary_api,
    ("primary", "test"):      run_primary_tests,
}

# Systems that support pre-authenticated GUI launch
_AUTH_GUI_SYSTEMS = {"university", "college", "school", "primary"}

# Systems that support pre-authenticated CLI launch
_AUTH_CLI_SYSTEMS = {"university", "college", "school", "primary"}


# ── CLI interactive menus ─────────────────────────────────────────────────────

def _flush_stdin():
    """Drain any leftover characters from stdin (e.g. after a tkinter dialog)."""
    import select
    try:
        while select.select([sys.stdin], [], [], 0.0)[0]:
            sys.stdin.readline()
    except Exception:
        pass


def cli_select_mode() -> str | None:
    """CLI menu: pick a run mode. Returns mode string or None to exit."""
    mapping = {"1": "cli", "2": "gui", "3": "api", "4": "test", "5": "test-all"}

    _flush_stdin()

    while True:
        print()
        print("=" * 54)
        print("       Education System Launcher")
        print("=" * 54)
        print()
        print("  [1] CLI    - Command-line interface")
        print("  [2] GUI    - Graphical interface")
        print("  [3] API    - REST API server (includes web dashboard)")
        print("  [4] Test   - Run test suite (single system)")
        print("  [5] Test   - Run ALL tests (all systems)")
        print("  [0] Exit")
        print()

        choice = input("  Select mode: ").strip()
        if choice == "0":
            print("\n  Goodbye!")
            return None
        if choice in mapping:
            return mapping[choice]
        print("\n  Invalid option. Please try again.")


def cli_select_system() -> str | None:
    """CLI menu: pick a system. Returns 'university', 'college', 'school' or None."""
    mapping = {"1": "university", "2": "college", "3": "school", "4": "primary"}

    _flush_stdin()

    while True:
        print()
        print("  ── Select System ──")
        print()
        print("  [1] University Management System")
        print("  [2] Sixth Form College System")
        print("  [3] Secondary School Management System")
        print("  [4] Primary School Management System")
        print("  [0] Back")
        print()

        choice = input("  Select system: ").strip()
        if choice == "0":
            return None
        if choice in mapping:
            return mapping[choice]
        print("\n  Invalid option. Please try again.")


# ── Main entry ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Education System Launcher",
        epilog="If no flags are given an interactive menu is shown.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--cli", action="store_true", help="Command-line interface")
    mode_group.add_argument("--gui", action="store_true", help="Graphical interface")
    mode_group.add_argument("--api", action="store_true", help="REST API server")
    mode_group.add_argument("--test", action="store_true", help="Run test suite")
    mode_group.add_argument("--test-all", action="store_true", help="Run tests for all systems")

    parser.add_argument("--seed", type=int, metavar="N", help="Seed database with N demo students")

    sys_group = parser.add_mutually_exclusive_group()
    sys_group.add_argument("--university", action="store_true", help="University system")
    sys_group.add_argument("--college", action="store_true", help="College system")
    sys_group.add_argument("--school", action="store_true", help="Secondary school system")
    sys_group.add_argument("--primary", action="store_true", help="Primary school system")

    args = parser.parse_args()

    # Resolve mode from flags
    mode = None
    if args.cli:
        mode = "cli"
    elif args.gui:
        mode = "gui"
    elif args.api:
        mode = "api"
    elif args.test:
        mode = "test"
    elif args.test_all:
        mode = "test-all"

    # Resolve system from flags
    system = None
    if args.university:
        system = "university"
    elif args.college:
        system = "college"
    elif args.school:
        system = "school"
    elif args.primary:
        system = "primary"

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

    # ── Unified i18n setup ──────────────────────────────────────────────
    # Show language selector before anything else.  For GUI mode we show a
    # tkinter dialog; for CLI / API / test we use the console selector.
    try:
        from education_system.shared.i18n import init_i18n, set_language, get_current_language

        if mode == "gui" or mode is None:
            # GUI selector (also covers the case where mode hasn't been chosen yet)
            from education_system.shared.i18n.selector_gui import show_language_selector
            chosen = show_language_selector()
            init_i18n(chosen)
        elif mode == "cli":
            from education_system.shared.i18n.selector_cli import show_language_selector_cli
            chosen = show_language_selector_cli()
            init_i18n(chosen)
        else:
            # api / test — just load saved preference silently
            init_i18n()
    except Exception as exc:
        logger.debug("i18n init skipped: %s", exc)

    # Interactive fallbacks
    if mode is None:
        mode = cli_select_mode()
        if mode is None:
            return

    # Handle test-all from interactive menu
    if mode == "test-all":
        success = run_all_system_tests()
        sys.exit(0 if success else 1)

    def _is_superadmin_user(uinfo):
        if not uinfo:
            return False
        systems = uinfo.get("systems", [])
        admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
        return admin_keys >= {"university", "college", "school", "primary"}

    # For GUI mode, use universal login (which handles system selection too)
    if mode == "gui" and system is None:
        result = gui_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result

        # Launch with switch dispatch loop
        while True:
            # Superadmin gets the cross-system dashboard
            if system == "__superadmin__":
                try:
                    from education_system.shared.gui.superadmin_dashboard import SuperAdminDashboard
                    dashboard = SuperAdminDashboard(user_info, shared_auth)
                    dashboard.mainloop()

                    if dashboard.logged_out:
                        result = gui_universal_login()
                        if result is None:
                            break
                        user_info, system, role, shared_auth = result
                        continue

                    if dashboard.launch_system:
                        system = dashboard.launch_system
                        role = dashboard.launch_role or "admin"
                        continue

                    break  # window closed without action
                except Exception as e:
                    logger.error(f"Superadmin dashboard error: {e}", exc_info=True)
                    print(f"\n  Dashboard error: {e}")
                    break

            launcher = LAUNCHERS.get((system, mode))
            if launcher is None:
                print(f"  Unknown combination: {system} + {mode}")
                sys.exit(1)

            try:
                if mode == "gui" and system in _AUTH_GUI_SYSTEMS:
                    launcher(user_info=user_info, role=role, shared_auth=shared_auth)
                else:
                    launcher()
            except KeyboardInterrupt:
                print("\n\n  Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                print(f"\n  Error: {e}")
                sys.exit(1)

            # Check if a system/mode switch was requested
            from education_system.switch import consume
            switch_request = consume()
            if switch_request is None:
                # Superadmin returns to dashboard after closing a system
                if _is_superadmin_user(user_info):
                    system = "__superadmin__"
                    continue
                break
            system, mode = switch_request

            # Logout requested — return to the universal login screen
            if system == "__login__":
                result = gui_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
                continue

            # Superadmin dashboard requested via switch
            if system == "__superadmin__":
                continue

            print(f"\n  Switching to {system} ({mode})...\n")

            # For GUI switches, check if the current user already has
            # access to the target system (e.g. superadmin) — if so,
            # skip the login screen and just update the role.
            if mode == "gui":
                target_role = None
                if user_info:
                    for s in user_info.get("systems", []):
                        if s["system_key"] == system:
                            target_role = s["role"]
                            break

                if target_role:
                    # User already has access — reuse session
                    role = target_role
                else:
                    # No access to target system — show login again
                    result = gui_universal_login()
                    if result is None:
                        break
                    user_info, system, role, shared_auth = result
        return

    # For CLI mode without a system specified, use universal CLI login
    if mode == "cli" and system is None:
        result = cli_universal_login()
        if result is None:
            return
        user_info, system, role, shared_auth = result

        # Launch with switch dispatch loop
        while True:
            # Superadmin CLI dashboard
            if system == "__superadmin__":
                try:
                    from education_system.shared.cli.superadmin_cli import run as superadmin_cli_run
                    result = superadmin_cli_run(user_info, shared_auth)
                    if result:
                        # Quick Launch selected — switch to that system
                        system, role = result
                        continue
                    else:
                        # Logged out — return to login
                        result = cli_universal_login()
                        if result is None:
                            break
                        user_info, system, role, shared_auth = result
                        continue
                except KeyboardInterrupt:
                    print("\n\n  Interrupted. Goodbye!")
                    break
                except Exception as e:
                    logger.error(f"Error: {e}", exc_info=True)
                    print(f"\n  Error: {e}")
                    sys.exit(1)

            launcher = LAUNCHERS.get((system, mode))
            if launcher is None:
                print(f"  Unknown combination: {system} + {mode}")
                sys.exit(1)

            try:
                if mode == "cli" and system in _AUTH_CLI_SYSTEMS:
                    launcher(user_info=user_info, role=role, shared_auth=shared_auth)
                else:
                    launcher()
            except KeyboardInterrupt:
                print("\n\n  Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                print(f"\n  Error: {e}")
                sys.exit(1)

            # Check if a system/mode switch was requested
            from education_system.switch import consume
            switch_request = consume()
            if switch_request is None:
                # If superadmin, return to dashboard instead of exiting
                if _is_superadmin_user(user_info):
                    system = "__superadmin__"
                    continue
                break
            system, mode = switch_request

            # Logout requested — return to universal CLI login
            if system == "__login__":
                result = cli_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
                continue

            print(f"\n  Switching to {system} ({mode})...\n")

            # For CLI switches, check if current user has access to the target
            if mode == "cli":
                target_role = None
                if user_info:
                    for s in user_info.get("systems", []):
                        if s["system_key"] == system:
                            target_role = s["role"]
                            break

                if target_role:
                    role = target_role
                else:
                    # No access to target system — show login again
                    result = cli_universal_login()
                    if result is None:
                        break
                    user_info, system, role, shared_auth = result
        return

    if mode == "api":
        run_unified_api()
        return

    # Non-CLI/GUI modes or system already specified: select system if needed
    while system is None:
        system = cli_select_system()
        if system is None:
            # User chose "Back" — return to mode selection
            mode = cli_select_mode()
            if mode is None:
                return
            # Handle test-all if re-selected
            if mode == "test-all":
                success = run_all_system_tests()
                sys.exit(0 if success else 1)
            continue

    # Launch with switch dispatch loop
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
            logger.error(f"Error: {e}", exc_info=True)
            print(f"\n  Error: {e}")
            sys.exit(1)

        # Check if a system/mode switch was requested
        from education_system.switch import consume
        switch_request = consume()
        if switch_request is None:
            break
        system, mode = switch_request
        print(f"\n  Switching to {system} ({mode})...\n")


if __name__ == "__main__":
    main()
