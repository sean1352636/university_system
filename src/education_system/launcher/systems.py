"""Per-system bootstrap and launcher functions, plus the dispatch table."""

import logging
import os
import subprocess
import sys

from education_system.launcher.auth import init_shared_auth, gui_universal_login

logger = logging.getLogger(__name__)


def _start_security_training_links() -> None:
    """Keep database-inbox training links live in every desktop system."""
    try:
        from education_system.platform.governance.security.training_simulation import (
            default_simulation,
        )
        default_simulation()
    except Exception as exc:
        logger.debug("Security-training invitation listener not started: %s", exc)


# ── University ───────────────────────────────────────────────────────────────

def _init_university():
    """One-time university system bootstrap (env, i18n, auth, DB)."""
    init_shared_auth()

    # No per-university .env is loaded here: the path this used to build
    # (``education_system/post_18/university_system/.env``) has not existed
    # since the ADR 0018 move, so the block never fired. run.py already loads
    # the repository-root .env before any bootstrap runs.

    from education_system.paths import ensure_university_directories
    ensure_university_directories()

    from education_system.systems.university.infrastructure.i18n import init_i18n
    try:
        from education_system.platform.features.i18n import get_current_language
        init_i18n(get_current_language())
    except Exception:
        init_i18n("en")

    from education_system.systems.university.infrastructure.auth import UserAuth
    from education_system.systems.university.infrastructure.shared_context import set_auth
    set_auth(UserAuth())

    from education_system.systems.university.infrastructure.defaults import print_generated_passwords
    print_generated_passwords()

    from education_system.systems.university.infrastructure.database.database_utils import init_db
    init_db()

    # Keep database-stored security-training links usable for every signed-in
    # university user.  In desktop mode there is no web API process, so the
    # localhost-only invitation endpoint must live for the lifetime of the app.
    # This also covers links copied from an inbox into a browser and campaigns
    # created during an earlier application session.
    _start_security_training_links()

    try:
        from education_system.systems.university.infrastructure.auth.migration_to_shared import migrate
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
        from education_system.systems.university.domains.admissions.domain.sixthform_intake import (
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
        from education_system.platform.integrations.external.bus_drainer import (
            start_background_drainer,
        )
        start_background_drainer("university")
    except Exception as exc:
        logger.debug("University background drainer not started: %s", exc)


def run_university_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.systems.university.infrastructure.i18n import init_i18n, get_text as _
    try:
        from education_system.platform.features.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_cli"))
    from education_system.systems.university.interfaces.cli.shell.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_university_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.systems.university.infrastructure.i18n import init_i18n, get_text as _
    try:
        from education_system.platform.features.i18n import get_current_language
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

    from education_system.systems.university.infrastructure.auth.core_utils.constants import PERMISSIONS
    uni_permissions = list(PERMISSIONS.get(uni_role, []))

    legacy_user_id = None
    student_id = None
    try:
        from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH))
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
    from education_system.systems.university.interfaces.gui.shell.main.main_gui import init_gui
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
    "sixth_form": "education_system.systems.sixth_form.domain.admissions.college_intake",
    "secondary":  "education_system.systems.secondary.domain.admissions.secondary_intake",
    "primary": "education_system.systems.primary.domain.learners.pupils.primary_intake",
}


# system_key -> dotted module path exposing register(); the system's side of
# the platform transition contract. Registering is what turns a recorded move
# into a real local record: without it the platform can still log that a
# learner went to apprenticeships, but has nobody to call to create the
# apprentice. Kept here rather than in each package's __init__ so importing a
# system never drags the platform's cross-system stack in behind it.
_PHASE_ADAPTERS = {
    "apprenticeships":
        "education_system.systems.apprenticeships.integrations.cross_system_adapter",
    "fe_college":
        "education_system.systems.fe_college.services.cross_system_adapter",
}


def _register_phase_adapter(system_key):
    """Register ``system_key``'s transition adapter with the platform.

    Best-effort and idempotent: a system whose adapter fails to load still
    launches, it just cannot receive learners until the cause is fixed —
    which is strictly better than refusing to start the whole system.
    """
    module_path = _PHASE_ADAPTERS.get(system_key)
    if not module_path:
        return
    try:
        import importlib
        importlib.import_module(module_path).register()
        logger.debug("Registered %s phase adapter", system_key)
    except Exception as exc:
        logger.warning(
            "%s phase adapter not registered (%s); cross-system transfers "
            "into this system will not create local records", system_key, exc)


def _drain_progression(system_key):
    """Drain pending cross-system progression transfers for ``system_key``
    from the durable bus (idempotent; safe if there's nothing waiting)."""
    _register_phase_adapter(system_key)
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
    elif system_key in _PHASE_ADAPTERS:
        # No bespoke intake module, but the system implements the adapter
        # contract — so its ``create_applicant`` is the intake. Systems
        # that joined the platform after the adapter contract existed use
        # this path instead of hand-writing a fourth intake module.
        try:
            from education_system.platform.cross_system import adapter_intake
            adapter_intake.drain(system_key)
        except Exception as exc:
            logger.debug("%s adapter intake skipped: %s", system_key, exc)
    # Promote the bus to a real-time backbone: a background thread keeps
    # draining while this system runs, so safeguarding / GDPR / parent
    # events propagate continuously rather than only at next launch.
    try:
        from education_system.platform.integrations.external.bus_drainer import (
            start_background_drainer,
        )
        start_background_drainer(system_key)
    except Exception as exc:
        logger.debug("%s background drainer not started: %s", system_key, exc)

def run_sixthform_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.sixth_form import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("sixth_form")
    _start_security_training_links()
    from education_system.systems.sixth_form.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_sixthform_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.sixth_form import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("sixth_form")
    _start_security_training_links()
    from education_system.systems.sixth_form.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.secondary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    _start_security_training_links()
    from education_system.systems.secondary.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.secondary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    _start_security_training_links()
    from education_system.systems.secondary.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.primary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("primary")
    _start_security_training_links()
    from education_system.systems.primary.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_primarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.primary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("primary")
    _start_security_training_links()
    from education_system.systems.primary.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_apprenticeships_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.apprenticeships import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("apprenticeships")
    _start_security_training_links()
    from education_system.systems.apprenticeships.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_apprenticeships_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.apprenticeships import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("apprenticeships")
    _start_security_training_links()
    from education_system.systems.apprenticeships.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_fecollege_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.fe_college import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("fe_college")
    _start_security_training_links()
    from education_system.systems.fe_college.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_fecollege_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.fe_college import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("fe_college")
    _start_security_training_links()
    from education_system.systems.fe_college.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_nursery_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.nursery import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    from education_system.systems.nursery.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_nursery_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.nursery import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    from education_system.systems.nursery.gui_main import run
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
    from education_system.platform.delivery.api.unified_server import run_unified_api as _run
    _run()


def run_university_tests():
    return _run_pytest("tests/unit/systems/university")


def run_sixthform_tests():
    return _run_pytest("tests/unit/systems/sixth_form")


def run_secondarysch_tests():
    return _run_pytest("tests/unit/systems/secondary")


def run_primarysch_tests():
    return _run_pytest("tests/unit/systems/primary")


def run_nursery_tests():
    return _run_pytest("tests/unit/systems/nursery")


def run_fecollege_tests():
    return _run_pytest("tests/unit/systems/fe_college")


def run_apprenticeships_tests():
    return _run_pytest("tests/unit/systems/apprenticeships")


def _run_pytest(test_dir):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-vv", "--tb=short", "-n0"],
        cwd=_repo_root(),
    )
    return result.returncode == 0


def _repo_root():
    """Return the repository root containing ``tests``."""
    from pathlib import Path
    return str(Path(__file__).resolve().parents[3])


def run_all_system_tests():
    """Run every system test suite from the consolidated tests tree."""
    test_dirs = ["tests/unit/systems"]
    print()
    print("=" * 60)
    print("  RUNNING ALL SYSTEM TESTS")
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
    from education_system.platform.kernel.seeding import DemoSeeder

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
    # Apprenticeships system — auth seed key is "apprenticeships". A full
    # cross-system member, but a post-16 destination beside the phase chain
    # rather than a step on it: secondary, sixth form and FE feed it, it runs
    # concurrently with university for a degree apprenticeship, and it feeds
    # back into university for a top-up. See progression.PARALLEL_SYSTEMS.
    ("apprenticeships", "cli"):  run_apprenticeships_cli,
    ("apprenticeships", "gui"):  run_apprenticeships_gui,
    ("apprenticeships", "test"): run_apprenticeships_tests,
    # FE College system — auth seed key is "fe_college". Now a full member of
    # the cross-system registry: its own student_journey slot, an entry in
    # paths.SYSTEM_DB_PATHS, and a PhaseAdapter, so learners move in and out
    # of it like any other system. Its intake is adapter-backed rather than a
    # bespoke module — see _drain_progression.
    ("fe_college", "cli"):  run_fecollege_cli,
    ("fe_college", "gui"):  run_fecollege_gui,
    ("fe_college", "test"): run_fecollege_tests,
}

# Systems that support pre-authenticated launch
AUTH_GUI_SYSTEMS = {
    "university", "sixth_form", "secondary", "primary", "nursery",
    "apprenticeships", "fe_college",
}
AUTH_CLI_SYSTEMS = {
    "university", "sixth_form", "secondary", "primary", "nursery",
    "apprenticeships", "fe_college",
}
