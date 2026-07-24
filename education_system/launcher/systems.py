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
            "post_18", "university_system", ".env",
        )
        if os.path.exists(env):
            load_dotenv(env)
    except ImportError:
        pass

    from education_system.post_18.university_system.core.paths import ensure_directories
    ensure_directories()

    from education_system.post_18.university_system.core.i18n import init_i18n
    try:
        from education_system.shared.i18n import get_current_language
        init_i18n(get_current_language())
    except Exception:
        init_i18n("en")

    from education_system.post_18.university_system.infrastructure.auth import UserAuth
    from education_system.post_18.university_system.infrastructure.shared_context import set_auth
    set_auth(UserAuth())

    from education_system.post_18.university_system.core.defaults import print_generated_passwords
    print_generated_passwords()

    from education_system.post_18.university_system.infrastructure.database.database_utils import init_db
    init_db()

    try:
        from education_system.post_18.university_system.infrastructure.auth.migration_to_shared import migrate
        migrate()
    except Exception as exc:
        logger.debug("University auth migration skipped: %s", exc)

    try:
        from education_system.launcher.auth import sync_university_mfa_to_shared
        sync_university_mfa_to_shared()
    except Exception as exc:
        logger.debug("University MFA sync skipped: %s", exc)

    # Drain any pending sixth-form progression transfers from the durable
    # cross-system bus (idempotent; safe if there's nothing waiting).
    try:
        from education_system.post_18.university_system.modules.domain.admissions.sixthform_intake import (
            drain_intake,
        )
        n = drain_intake()
        if n:
            logger.info("Admitted %d sixth-form transfer(s) from the bus", n)
    except Exception as exc:
        logger.debug("Sixth-form intake drain skipped: %s", exc)

    # Keep draining in the background so cross-system events (safeguarding,
    # GDPR, parent linkage) reach the university while it's running.
    try:
        from education_system.shared.integrations.bus_drainer import (
            start_background_drainer,
        )
        start_background_drainer("university")
    except Exception as exc:
        logger.debug("University background drainer not started: %s", exc)


def run_university_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.post_18.university_system.core.i18n import init_i18n, get_text as _
    try:
        from education_system.shared.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_cli"))
    from education_system.post_18.university_system.modules.shared.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_university_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.post_18.university_system.core.i18n import init_i18n, get_text as _
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

    from education_system.post_18.university_system.infrastructure.auth.core_utils.constants import PERMISSIONS
    uni_permissions = list(PERMISSIONS.get(uni_role, []))

    legacy_user_id = None
    student_id = None
    try:
        from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
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
    from education_system.post_18.university_system.modules.shared.gui.main.main_gui import init_gui
    app = init_gui(session_user=session_user)
    app.run()


# ── Sixth Form / Secondary / Primary ────────────────────────────────────────
#
# These systems use the shared (universal) login. The `UserAuth` returned
# by `gui_universal_login` / `cli_universal_login` already has `current_user`
# populated, so we pass it straight through as `shared_auth` — no per-system
# login dialog runs.

# system_key -> dotted module path exposing drain_intake(); these admit any
# pupils who progressed from the previous phase off the durable bus.
_PROGRESSION_INTAKES = {
    "sixth_form": "education_system.post_16.sixthform_system.modules.domain.students.college_intake",
    "secondary":  "education_system.secondarysch_system.modules.domain.pupils.secondary_intake",
    "primary": "education_system.primarysch_system.modules.domain.pupils.primary_intake",
}


def _drain_progression(system_key):
    """Drain pending cross-system progression transfers for ``system_key``
    from the durable bus (idempotent; safe if there's nothing waiting)."""
    module_path = _PROGRESSION_INTAKES.get(system_key)
    if module_path:
        try:
            import importlib
            module = importlib.import_module(module_path)
            n = module.drain_intake()
            if n:
                logger.info("Admitted %d %s transfer(s) from the bus",
                            n, system_key)
        except Exception as exc:
            logger.debug("%s intake drain skipped: %s", system_key, exc)
    # Promote the bus to a real-time backbone: a background thread keeps
    # draining while this system runs, so safeguarding / GDPR / parent
    # events propagate continuously rather than only at next launch.
    try:
        from education_system.shared.integrations.bus_drainer import (
            start_background_drainer,
        )
        start_background_drainer(system_key)
    except Exception as exc:
        logger.debug("%s background drainer not started: %s", system_key, exc)

def run_sixthform_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.post_16.sixthform_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("sixth_form")
    from education_system.post_16.sixthform_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_sixthform_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.post_16.sixthform_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("sixth_form")
    from education_system.post_16.sixthform_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.secondarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    from education_system.secondarysch_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.secondarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    from education_system.secondarysch_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.primarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("primary")
    from education_system.primarysch_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.primarysch_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("primary")
    from education_system.primarysch_system.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_nursery_cli(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.nursery_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.nursery_system.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_nursery_gui(user_info=None, role=None, shared_auth=None):
    from education_system.shared import branding
    from education_system.nursery_system import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    from education_system.nursery_system.main_gui import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


# ── Shared ───────────────────────────────────────────────────────────────────

def run_unified_api():
    # The interactive launcher is a local/dev entry point. If the operator
    # hasn't explicitly declared an environment, default to development so the
    # server starts with the built-in localhost-only CORS fallback instead of
    # refusing to boot. Real deployments set APP_ENV=production (and an explicit
    # API_CORS_ORIGINS), which is left untouched here.
    if not os.getenv("APP_ENV"):
        os.environ["APP_ENV"] = "development"
    from education_system.shared.api.unified_server import run_unified_api as _run
    _run()


def run_university_tests():
    from education_system.post_18.university_system.tests.run_all_tests import run_all_tests
    return run_all_tests()


def run_sixthform_tests():
    return _run_pytest("education_system/sixthform_system/tests/")


def run_secondarysch_tests():
    return _run_pytest("education_system/secondarysch_system/tests/")


def run_primarysch_tests():
    return _run_pytest("education_system/primarysch_system/tests/")


def run_nursery_tests():
    return _run_pytest("education_system/nursery_system/tests/")


def _run_pytest(test_dir):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-vv", "--tb=short", "-n0"],
        cwd=_repo_root(),
    )
    return result.returncode == 0


def _repo_root():
    """Return the repository root (three levels up from this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_system_tests():
    """Run the university test suite."""
    test_dirs = ["education_system/post_18/university_system/tests/"]
    print()
    print("=" * 60)
    print("  RUNNING UNIVERSITY TESTS")
    print("=" * 60)
    print()
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + test_dirs + [
            "-vv", "--tb=short", "-ra", "--color=yes", "-n0",
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
    # Sixth-form system — auth seed key is "sixth_form"
    ("sixth_form", "cli"):     run_sixthform_cli,
    ("sixth_form", "gui"):     run_sixthform_gui,
    ("sixth_form", "test"):    run_sixthform_tests,
    # Secondary school system — auth seed key is "secondary"
    ("secondary", "cli"):      run_secondarysch_cli,
    ("secondary", "gui"):      run_secondarysch_gui,
    ("secondary", "test"):     run_secondarysch_tests,
    # Primary school system — auth seed key is "primary"
    ("primary", "cli"):     run_primarysch_cli,
    ("primary", "gui"):     run_primarysch_gui,
    ("primary", "test"):    run_primarysch_tests,
    # Nursery system — auth seed key is "nursery"
    ("nursery", "cli"):     run_nursery_cli,
    ("nursery", "gui"):     run_nursery_gui,
    ("nursery", "test"):    run_nursery_tests,
}

# Systems that support pre-authenticated launch
AUTH_GUI_SYSTEMS = {"university", "sixth_form", "secondary", "primary", "nursery"}
AUTH_CLI_SYSTEMS = {"university", "sixth_form", "secondary", "primary", "nursery"}
