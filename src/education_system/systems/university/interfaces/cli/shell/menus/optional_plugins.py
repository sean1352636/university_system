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
        "education_system.systems.university.domain.operations.reporting."
        "kpi_dashboard.cli.kpi_dashboard_cli",
        "display_kpi_dashboard_menu",
    ),
    "nf_institutional_analytics": (
        "education_system.systems.university.domain.operations.reporting."
        "institutional_analytics.cli.institutional_analytics_cli",
        "display_institutional_analytics_menu",
    ),
    "nf_bursary": (
        "education_system.systems.university.domains.finance.domain."
        "bursary.cli.bursary_cli",
        "display_bursary_menu",
    ),
    "nf_mentoring_matching": (
        "education_system.systems.university.domains.pastoral.domain."
        "student_union.services.mentoring_matching.cli.matching_cli",
        "display_mentoring_matching_menu",
    ),
    "nf_room_booking": (
        "education_system.systems.university.domain.operations.campus."
        "room_booking.cli.room_booking_cli",
        "display_room_booking_menu",
    ),
    "nf_tutor_groups": (
        "education_system.systems.university.domain.academics."
        "tutor_groups.cli.tutor_group_cli",
        "display_tutor_group_menu",
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
