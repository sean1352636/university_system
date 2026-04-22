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


# ── College ──────────────────────────────────────────────────────────────────

def _init_college_i18n():
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


# ── Secondary School ─────────────────────────────────────────────────────────

def run_school_cli(user_info=None, role=None, shared_auth=None):
    from education_system.secondary_school.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_school_gui(user_info=None, role=None, shared_auth=None):
    from education_system.secondary_school.modules.shared.gui.main_gui import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


# ── Primary School ───────────────────────────────────────────────────────────

def run_primary_cli(user_info=None, role=None, shared_auth=None):
    from education_system.primary_school.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primary_gui(user_info=None, role=None, shared_auth=None):
    from education_system.primary_school.modules.shared.gui.main_gui import run
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


def run_college_tests():
    return _run_pytest("education_system/college_system/tests/")


def run_school_tests():
    return _run_pytest("education_system/secondary_school/tests/")


def run_primary_tests():
    return _run_pytest("education_system/primary_school/tests/")


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
        cwd=_repo_root(),
    )
    return result.returncode == 0


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

    seed_dir = Path(__file__).resolve().parent.parent.parent / "education_system" / "shared" / "data" / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)

    exporter = StudentDataExporter(system_name=system.title(), system_key=system)
    exporter.save(seed_dir / f"{system}_students.json", students)
    exporter.save(seed_dir / f"{system}_students.csv", students)
    print(f"\n  Saved to: {seed_dir}/")
    print()


# ── Dispatch Table ───────────────────────────────────────────────────────────

LAUNCHERS = {
    ("university", "cli"):  run_university_cli,
    ("university", "gui"):  run_university_gui,
    ("university", "api"):  run_unified_api,
    ("university", "test"): run_university_tests,
    ("college", "cli"):     run_college_cli,
    ("college", "gui"):     run_college_gui,
    ("college", "api"):     run_unified_api,
    ("college", "test"):    run_college_tests,
    ("school", "cli"):      run_school_cli,
    ("school", "gui"):      run_school_gui,
    ("school", "api"):      run_unified_api,
    ("school", "test"):     run_school_tests,
    ("primary", "cli"):     run_primary_cli,
    ("primary", "gui"):     run_primary_gui,
    ("primary", "api"):     run_unified_api,
    ("primary", "test"):    run_primary_tests,
}

# Systems that support pre-authenticated launch
AUTH_GUI_SYSTEMS = {"university", "college", "school", "primary"}
AUTH_CLI_SYSTEMS = {"university", "college", "school", "primary"}
