"""Per-system bootstrap and launcher functions, plus the dispatch table."""

import logging
import os
import subprocess
import sys

from education_system.launcher.auth import init_shared_auth, gui_universal_login

logger = logging.getLogger(__name__)


# ── University ───────────────────────────────────────────────────────────────

def _init_university():
    """One-time university system bootstrap (env, i18n, auth, DB)."""
    init_shared_auth()

    try:
        from dotenv import load_dotenv
        env = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..",
            "university_system", ".env",
        )
        if os.path.exists(env):
            load_dotenv(env)
    except ImportError:
        pass

    from education_system.university_system.modules.shared.constants.paths import ensure_directories
    ensure_directories()

    from education_system.university_system.modules.shared.utils.i18n import init_i18n
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

    try:
        from education_system.university_system.infrastructure.auth.migration_to_shared import migrate
        migrate()
    except Exception as exc:
        logger.debug("University auth migration skipped: %s", exc)

    try:
        from education_system.launcher.auth import sync_university_mfa_to_shared
        sync_university_mfa_to_shared()
    except Exception as exc:
        logger.debug("University MFA sync skipped: %s", exc)


def run_university_cli(user_info=None, role=None, shared_auth=None):
    _init_university()
    from education_system.university_system.modules.shared.utils.i18n import init_i18n, get_text as _
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
    try:
        from education_system.shared.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_gui"))

    if not user_info or not shared_auth:
        result = gui_universal_login()
        if result is None:
            return
        user_info, _sys, role, shared_auth = result

    # Honour an explicit role argument (set by the superadmin role picker);
    # otherwise resolve from the user's stored systems list.
    if role:
        uni_role = role
    else:
        uni_role = "student"
        for s in user_info.get("systems", []):
            if s["system_key"] == "university":
                uni_role = s["role"]
                break

    from education_system.university_system.infrastructure.auth.core_utils.constants import PERMISSIONS
    uni_permissions = list(PERMISSIONS.get(uni_role, []))

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


# ── Sixth Form / Secondary / Primary ────────────────────────────────────────
#
# These systems use the shared (universal) login. The `UserAuth` returned
# by `gui_universal_login` / `cli_universal_login` already has `current_user`
# populated, so we pass it straight through as `shared_auth` — no per-system
# login dialog runs.

def run_sixthform_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.sixthform_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.sixthform_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_sixthform_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.sixthform_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.sixthform_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.secondarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.secondarysch_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.secondarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.secondarysch_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.primarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.primarysch_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.primarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.primarysch_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


# ── Shared ───────────────────────────────────────────────────────────────────

def run_unified_api():
    from education_system.shared.api.unified_server import run_unified_api as _run
    _run()


def run_university_tests():
    from education_system.university_system.tests.run_all_tests import run_all_tests
    return run_all_tests()


def _run_pytest(test_dir):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short"],
        cwd=_repo_root(),
    )
    return result.returncode == 0


def _repo_root():
    """Return the repository root (three levels up from this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_system_tests():
    """Run the university test suite."""
    test_dirs = ["education_system/university_system/tests/"]
    print()
    print("=" * 60)
    print("  RUNNING UNIVERSITY TESTS")
    print("=" * 60)
    print()
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + test_dirs + [
            "-v", "--tb=short", "-ra", "--color=yes",
        ],
        cwd=_repo_root(),
    )
    return result.returncode == 0


def run_seed(system: str, count: int):
    """Seed the university system with demo data."""
    from education_system.shared.seeding import DemoSeeder

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
    print()


# ── Dispatch Table ───────────────────────────────────────────────────────────

LAUNCHERS = {
    ("university", "cli"):  run_university_cli,
    ("university", "gui"):  run_university_gui,
    ("university", "api"):  run_unified_api,
    ("university", "test"): run_university_tests,
    # Sixth-form system — auth seed key is "college"
    ("college", "cli"):     run_sixthform_cli,
    ("college", "gui"):     run_sixthform_gui,
    # Secondary school system — auth seed key is "school"
    ("school", "cli"):      run_secondarysch_cli,
    ("school", "gui"):      run_secondarysch_gui,
    # Primary school system — auth seed key is "primary"
    ("primary", "cli"):     run_primarysch_cli,
    ("primary", "gui"):     run_primarysch_gui,
}

# Systems that support pre-authenticated launch
AUTH_GUI_SYSTEMS = {"university", "college", "school", "primary"}
AUTH_CLI_SYSTEMS = {"university", "college", "school", "primary"}
