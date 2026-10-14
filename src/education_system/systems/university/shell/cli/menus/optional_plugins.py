"""Component extracted from the legacy menu router."""
from __future__ import annotations

_NEW_FEATURE_CLI_DISPATCH = {
    "nf_employer_portal": (
        "education_system.systems.university.domains.progression.interfaces.cli."
        "employer_portal.employer_portal_cli",
        "display_employer_portal_menu",
    ),
    "nf_intervention_outcomes": (
        "education_system.systems.university.domains.pastoral.domain."
        "services.early_warning.outcomes.intervention_outcomes_cli",
        "display_intervention_outcomes_menu",
    ),
    "nf_kpi_dashboard": (
        "education_system.systems.university.domains.operations.interfaces.cli."
        "reporting.kpi_dashboard.kpi_dashboard_cli",
        "display_kpi_dashboard_menu",
    ),
    "nf_institutional_analytics": (
        "education_system.systems.university.domains.operations.interfaces.cli."
        "reporting.institutional_analytics.institutional_analytics_cli",
        "display_institutional_analytics_menu",
    ),
    "nf_bursary": (
        "education_system.systems.university.domains.finance.interfaces.cli."
        "bursary.bursary_cli",
        "display_bursary_menu",
    ),
    "nf_mentoring_matching": (
        "education_system.systems.university.domains.pastoral.interfaces.cli."
        "student_life.student_union.services.mentoring_matching.matching_cli",
        "display_mentoring_matching_menu",
    ),
    "nf_room_booking": (
        "education_system.systems.university.domains.operations.interfaces.cli."
        "campus.room_booking.room_booking_cli",
        "display_room_booking_menu",
    ),
    "nf_programme_governance": (
        "education_system.systems.university.domains.academics.interfaces.cli."
        "programme_governance.programme_governance_cli",
        "display_programme_governance_menu",
    ),
    "nf_pgr_admin": (
        "education_system.systems.university.domains.academics.interfaces.cli."
        "research.pgr.pgr_cli",
        "display_pgr_menu",
    ),
    "nf_assessment_boards": (
        "education_system.systems.university.domains.assessment.interfaces.cli."
        "boards.assessment_boards_cli",
        "display_assessment_boards_menu",
    ),
    "nf_case_management": (
        "education_system.systems.university.domains.governance.interfaces.cli."
        "case_management.case_management_cli",
        "display_case_management_menu",
    ),
    "nf_timetabling": (
        "education_system.systems.university.domains.academics.interfaces.cli."
        "timetabling.timetabling_cli",
        "display_timetabling_menu",
    ),
    "nf_identity_management": (
        "education_system.systems.university.domains.learners.interfaces.cli."
        "identity_management.identity_management_cli",
        "display_identity_management_menu",
    ),
    "nf_sso_providers": (
        "education_system.systems.university.shell.cli.auth.sso_providers_cli",
        "display_sso_providers_menu",
    ),
}

def _dispatch_new_feature(option, auth):
    """Resolve a new-feature option key to its CLI menu and run it."""
    target = _NEW_FEATURE_CLI_DISPATCH.get(option)
    if not target:
        print(f"\n  Unknown new feature: {option}")
        input("Press Enter to continue...")
        return
    module_path, fn_name = target
    try:
        import importlib
        mod = importlib.import_module(module_path)
        if hasattr(mod, "set_auth"):
            mod.set_auth(auth)
        fn = getattr(mod, fn_name)
        fn()
    except Exception as e:
        print(f"\n  Failed to launch new feature ({option}): {e}")
        input("Press Enter to continue...")
