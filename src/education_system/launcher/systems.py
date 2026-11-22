"""Per-system bootstrap and launcher functions, plus the dispatch table."""

import logging
import subprocess
import sys

from education_system.launcher.auth import gui_universal_login, init_shared_auth
from education_system.launcher.environment import apply_launcher_env_defaults

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
    # since the ADR 0018 move, so the block never fired. python -m education_system already loads
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

    from education_system.systems.university.infrastructure.defaults import (
        print_generated_passwords,
    )
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
        from education_system.systems.university.infrastructure.auth.migration_to_shared import (
            migrate,
        )
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

    try:
        from education_system.platform.integrations.external import cross_system_bus
        from education_system.systems.university.services.bus import (
            degree_apprenticeship_events,
        )
        degree_apprenticeship_events.register_consumers()
        cross_system_bus.poll_and_dispatch("university")
    except Exception as exc:
        logger.debug("Degree-apprenticeship university intake skipped: %s", exc)

    # Link students' own logins to their platform learner records, catching
    # up accounts from before linking was automatic. (The university does
    # not run ``_drain_progression``, which does this for the others.)
    try:
        from education_system.platform.cross_system import login_links
        login_links.try_sync_all(systems=["university"])
    except Exception as exc:
        logger.debug("University login links not synced: %s", exc)

    # Keep draining in the background so cross-system events (safeguarding,
    # GDPR, parent linkage) reach the university while it's running.
    try:
        from education_system.platform.integrations.external.bus_drainer import (
            start_background_drainer,
        )
        start_background_drainer("university")
    except Exception as exc:
        logger.debug("University background drainer not started: %s", exc)

    # Deliver the university e-mail outbox (retries, retention purge).
    try:
        from education_system.systems.university.infrastructure.email import outbox_delivery
        outbox_delivery.start_worker()
    except Exception as exc:
        logger.debug("University e-mail worker not started: %s", exc)

    # The university event outbox (provisioning retries, erasure requests,
    # the institutional connector feeds) and the student lifecycle actions
    # (fees, modules, visa, housing, library and sign-in after a status change).
    try:
        from education_system.systems.university.application import outbox_dispatcher
        outbox_dispatcher.start_worker()
    except Exception as exc:
        logger.debug("University outbox dispatcher not started: %s", exc)

    # General daily jobs (degree audit, ungraded exams, mailroom, attendance
    # risk, record retention, safeguarding digest / SLA alerts) and the
    # safeguarding e-mail retry every fifteen minutes.
    try:
        from education_system.systems.university.services.bus.jobs import university_jobs
        university_jobs.start_worker()
    except Exception as exc:
        logger.debug("University jobs worker not started: %s", exc)

    # Timed e-mails: library return reminders and overdue notices, ticket
    # satisfaction surveys, visa-expiry alerts and the compliance KPI refresh.
    try:
        from education_system.systems.university.infrastructure.email import email_scheduler
        email_scheduler.start_scheduler()
    except Exception as exc:
        logger.debug("University e-mail scheduler not started: %s", exc)

    # Scheduled batch work: watched folders at their daily time, batch reports.
    try:
        from education_system.systems.university.infrastructure.batch import scheduler
        scheduler.start_worker()
    except Exception as exc:
        logger.debug("University batch scheduler not started: %s", exc)

    # Academic integrity daily jobs: remove submitted text past the retention
    # period, send review / case / deadline reminders, close cases whose appeal
    # period has passed, and retry failed automatic similarity checks.
    try:
        from education_system.systems.university.infrastructure.integrity import retention_worker
        retention_worker.start_worker()
    except Exception as exc:
        logger.debug("University integrity daily worker not started: %s", exc)

    # Daily health jobs: the retention purge (only when a health retention
    # policy has auto_delete = 1), first aid reminders (certificates, RIDDOR
    # deadlines, kit/AED checks) and medical accommodation reconciliation.
    try:
        from education_system.systems.university.domains.health.infrastructure.health import (
            retention_worker as health_retention_worker,
        )
        health_retention_worker.start_worker()
    except Exception as exc:
        logger.debug("University health retention worker not started: %s", exc)

    # Trip jobs: waiting-list offer expiry and T-7 / T-1 reminders (hourly);
    # retention purge of participants' personal details, sealing of any
    # plain-text medical values and trip attendance (daily).
    try:
        from education_system.systems.university.services.bus.jobs import trip_jobs
        trip_jobs.start_worker()
    except Exception as exc:
        logger.debug("University trip jobs worker not started: %s", exc)

    # Student Support / Helpdesk jobs: escalation rules every five minutes
    # (each rule acts on a ticket once), the support metrics hourly.
    try:
        from education_system.systems.university.services.bus.jobs import support_jobs
        support_jobs.start_worker()
    except Exception as exc:
        logger.debug("University support jobs worker not started: %s", exc)

    # Staff HR jobs (daily): HR reminders (contract ends, probation, onboarding,
    # right to work / DBS, documents), certification expiry, leave year, increments.
    try:
        from education_system.systems.university.services.bus.jobs import staff_hr_jobs
        staff_hr_jobs.start_worker()
    except Exception as exc:
        logger.debug("University Staff HR jobs worker not started: %s", exc)

    # UCAS results day: apply confirmations held under the results embargo
    # once every result they rely on is published (every 15 minutes).
    try:
        from education_system.systems.university.services.bus.jobs import ucas_results_jobs
        ucas_results_jobs.start_worker()
    except Exception as exc:
        logger.debug("University results-day hold job not started: %s", exc)

    # Health clinic reminders: hourly 24h/2h appointment reminders (every
    # clinic), feedback requests, screening reminders, waiting-list offers.
    try:
        from education_system.systems.university.domains.health.infrastructure.health import (
            reminder_worker as health_reminder_worker,
        )
        health_reminder_worker.start_worker()
    except Exception as exc:
        logger.debug("University health reminder worker not started: %s", exc)


def run_university_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.systems.university.infrastructure.i18n import get_text as _
    from education_system.systems.university.infrastructure.i18n import init_i18n
    try:
        from education_system.platform.features.i18n import get_current_language
        lang = get_current_language()
    except Exception:
        lang = "en"
    init_i18n(lang)
    print(_("startup.starting_cli"))
    from education_system.systems.university.shell.cli.cli_main import main
    main(user_info=user_info, role=role, shared_auth=shared_auth)


def run_university_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    branding.set_system_name("University System")
    _init_university()
    from education_system.systems.university.infrastructure.i18n import get_text as _
    from education_system.systems.university.infrastructure.i18n import init_i18n
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

    # Shared with the university CLI so the two interfaces cannot drift on how
    # a shared-login session becomes a university user.
    from education_system.systems.university.infrastructure.auth.session_user import (
        build_session_user,
    )
    from education_system.systems.university.infrastructure.shared_context import (
        get_auth as _get_uni_auth,
    )
    session_user = build_session_user(
        user_info, uni_role, getattr(_get_uni_auth(), "permission_manager", None)
    )
    from education_system.systems.university.shell.gui.main.main_gui import init_gui
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
    "nursery":
        "education_system.systems.nursery.domain.learners.children.cross_system_adapter",
    "primary":
        "education_system.systems.primary.domain.learners.pupils.cross_system_adapter",
    "secondary":
        "education_system.systems.secondary.infrastructure.integrations.cross_system_adapter",
    "sixth_form":
        "education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter",
    "apprenticeships":
        "education_system.systems.apprenticeships.infrastructure.integrations.cross_system_adapter",
    "fe_college":
        "education_system.systems.fe_college.services.cross_system_adapter",
    "university":
        "education_system.systems.university.domains.admissions.domain.cross_system_adapter",
    "alternative_provision":
        "education_system.systems.alternative_provision.infrastructure.cross_system_adapter",
    "special_education":
        "education_system.systems.special_education.infrastructure.cross_system_adapter",
    "adult_education":
        "education_system.systems.adult_education.infrastructure.cross_system_adapter",
    "training_provider":
        "education_system.systems.training_provider.infrastructure.cross_system_adapter",
    "local_authority":
        "education_system.systems.local_authority.infrastructure.cross_system_adapter",
}


def declare_phase_adapters():
    """Tell the platform registry where every system's adapter lives.

    Declaring imports nothing from the systems. The registry loads an
    adapter the first time a route needs it, so the launched system can
    reach the other end of a boundary — primary moving a pupil needs the
    secondary adapter — without every system importing every other.
    """
    from education_system.platform.cross_system.adapters import registry
    for key, module_path in _PHASE_ADAPTERS.items():
        registry.declare(key, module_path)


declare_phase_adapters()


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
    if system_key == "apprenticeships":
        try:
            from education_system.platform.integrations.external import cross_system_bus
            from education_system.systems.apprenticeships.infrastructure.integrations import (
                degree_events,
            )
            degree_events.register_consumers()
            cross_system_bus.poll_and_dispatch("apprenticeships")
        except Exception as exc:
            logger.debug("Degree academic projection drain skipped: %s", exc)
    # Link learners' own logins to their platform learner records, catching
    # up accounts and records from before linking was automatic. A system
    # whose adapter does not pair logins is a no-op.
    try:
        from education_system.platform.cross_system import login_links
        login_links.try_sync_all(systems=[system_key])
    except Exception as exc:
        logger.debug("%s login links not synced: %s", system_key, exc)
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
    from education_system.systems.sixth_form.interfaces.cli.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_sixthform_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.sixth_form import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("sixth_form")
    _start_security_training_links()
    from education_system.systems.sixth_form.interfaces.gui.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_cli(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.secondary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    _start_security_training_links()
    from education_system.systems.secondary.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_secondarysch_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.secondary import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("secondary")
    _start_security_training_links()
    from education_system.systems.secondary.app.gui_main import run
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
    from education_system.systems.apprenticeships.interfaces.cli.shell import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_apprenticeships_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.apprenticeships import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _drain_progression("apprenticeships")
    _start_security_training_links()
    from education_system.systems.apprenticeships.interfaces.gui.gui_main import run
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


def run_special_education_cli(user_info=None, role=None, shared_auth=None):
    # No _drain_progression: SEND has a learner adapter (school requests and
    # EHCP updates, platform.cross_system.send_referrals) but no
    # SYSTEM_DB_PATHS entry, so it isn't a full cross-system member.
    from education_system.platform import branding
    from education_system.systems.special_education import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("special_education")
    from education_system.systems.special_education.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_special_education_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.special_education import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("special_education")
    from education_system.systems.special_education.app.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_adult_education_cli(user_info=None, role=None, shared_auth=None):
    # Linked to FE College and University through its adapter (referrals
    # both ways with FE, Access to HE applications to university); no
    # progression intake to drain and no SYSTEM_DB_PATHS entry yet.
    from education_system.platform import branding
    from education_system.systems.adult_education import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("adult_education")
    from education_system.systems.adult_education.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_adult_education_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.adult_education import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("adult_education")
    from education_system.systems.adult_education.app.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_alternative_provision_cli(user_info=None, role=None, shared_auth=None):
    # Linked to primary and secondary through its adapter (school referrals
    # in, reintegration out); no progression intake to drain and no
    # SYSTEM_DB_PATHS entry yet.
    from education_system.platform import branding
    from education_system.systems.alternative_provision import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("alternative_provision")
    from education_system.systems.alternative_provision.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_alternative_provision_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.alternative_provision import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("alternative_provision")
    from education_system.systems.alternative_provision.app.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_training_provider_cli(user_info=None, role=None, shared_auth=None):
    # Linked to Apprenticeships and FE College through its adapter (training
    # requests in, progression out); no progression intake to drain and no
    # SYSTEM_DB_PATHS entry yet.
    from education_system.platform import branding
    from education_system.systems.training_provider import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("training_provider")
    from education_system.systems.training_provider.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_training_provider_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.training_provider import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("training_provider")
    from education_system.systems.training_provider.app.gui_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_local_authority_cli(user_info=None, role=None, shared_auth=None):
    # No _drain_progression: Local Authority has a learner adapter (linked to
    # Primary and Secondary) but no SYSTEM_DB_PATHS entry.
    from education_system.platform import branding
    from education_system.systems.local_authority import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("local_authority")
    from education_system.systems.local_authority.app.cli_main import run
    run(user_info=user_info, role=role, shared_auth=shared_auth)


def run_local_authority_gui(user_info=None, role=None, shared_auth=None):
    from education_system.platform import branding
    from education_system.systems.local_authority import SYSTEM_NAME
    branding.set_system_name(SYSTEM_NAME)
    _start_security_training_links()
    _register_phase_adapter("local_authority")
    from education_system.systems.local_authority.app.gui_main import run
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
    # Normally already applied by launcher.main at import; repeated here because
    # this function is also reachable by importing launcher.systems directly,
    # and without a declared environment the server refuses to boot rather than
    # falling back to localhost-only CORS. Idempotent, and never overrides an
    # APP_ENV a real deployment has set.
    apply_launcher_env_defaults()
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


def run_special_education_tests():
    return _run_pytest("tests/unit/systems/special_education")


def run_adult_education_tests():
    return _run_pytest("tests/unit/systems/adult_education")


def run_alternative_provision_tests():
    return _run_pytest("tests/unit/systems/alternative_provision")


def run_training_provider_tests():
    return _run_pytest("tests/unit/systems/training_provider")


def run_local_authority_tests():
    return _run_pytest("tests/unit/systems/local_authority")


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
    # Special Education (SEND) — auth seed key is "special_education". Signed
    # in like the others, but not a cross-system member yet.
    ("special_education", "cli"):  run_special_education_cli,
    ("special_education", "gui"):  run_special_education_gui,
    ("special_education", "test"): run_special_education_tests,
    # Adult Education — auth seed key is "adult_education". Signed in like the
    # others, but not a cross-system member yet.
    ("adult_education", "cli"):  run_adult_education_cli,
    ("adult_education", "gui"):  run_adult_education_gui,
    ("adult_education", "test"): run_adult_education_tests,
    # Alternative Provision — auth seed key is "alternative_provision". Signed
    # in like the others, but not a cross-system member yet.
    ("alternative_provision", "cli"):  run_alternative_provision_cli,
    ("alternative_provision", "gui"):  run_alternative_provision_gui,
    ("alternative_provision", "test"): run_alternative_provision_tests,
    # Training Provider — auth seed key is "training_provider". Signed in like
    # the others, but not a cross-system member yet.
    ("training_provider", "cli"):  run_training_provider_cli,
    ("training_provider", "gui"):  run_training_provider_gui,
    ("training_provider", "test"): run_training_provider_tests,
    # Local Authority Education — auth seed key is "local_authority". Signed in
    # like the others, but not a cross-system member yet.
    ("local_authority", "cli"):  run_local_authority_cli,
    ("local_authority", "gui"):  run_local_authority_gui,
    ("local_authority", "test"): run_local_authority_tests,
}

# Systems that support pre-authenticated launch
AUTH_GUI_SYSTEMS = {
    "university", "sixth_form", "secondary", "primary", "nursery",
    "apprenticeships", "fe_college", "special_education", "adult_education",
    "alternative_provision", "training_provider", "local_authority",
}
AUTH_CLI_SYSTEMS = {
    "university", "sixth_form", "secondary", "primary", "nursery",
    "apprenticeships", "fe_college", "special_education", "adult_education",
    "alternative_provision", "training_provider", "local_authority",
}
