"""Import-boundary tests for the Pastoral vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Pastoral currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.

At 132 entries this is by far the largest allow-list, which is proportionate:
Pastoral is 699 modules, more than the first five migrated slices combined. It
is also the most *concentrated* — 56 of the 132 are one import of one Finance
module, and 32 are domain packages re-exporting their own CLI or GUI.

**Not visible to these rules.** The document requires that "medical data
repositories stay private to this slice; safeguarding referrals cross the
boundary through an explicit port/event, never a table import". No Pastoral
module imports Safeguarding today — but Safeguarding's
``services/integrations.py`` reads ``pastoral.health.wellness`` directly, and
Admissions' ``sixthform_intake`` and Learners' ``student_crud_gui`` both read
``pastoral.health.records``. Those are recorded in *their* slices' allow-lists;
the port belongs on this side of the boundary.
"""

from __future__ import annotations

SLICE = "pastoral"

_UNI = "education_system.systems.university"
_FIN = f"{_UNI}.domains.finance"
_LEGACY = f"{_UNI}.domain"
_ACAD = f"{_UNI}.domains.academics"
_OPS = f"{_UNI}.domains.operations"

#: Student-union commerce, clubs, events and trips all post payments through
#: Finance's integration module — 56 modules importing one target. This is the
#: single largest cluster in the whole migration, and the single highest-value
#: port: one published "charge raised" event would retire all 56.
_FINANCE_INTEGRATION = f"{_FIN}.infrastructure.finance_integration"

_FINANCE_INTEGRATION_CALLERS = {
    "domain/health/portal/dentist_cli.py",
    "interfaces/gui/student_union_gui/academic/academic_support.py",
    "interfaces/gui/student_union_gui/academic/resources.py",
    "interfaces/gui/student_union_gui/academic/study_groups.py",
    "interfaces/gui/student_union_gui/academic/tutoring.py",
    "interfaces/gui/student_union_gui/admin/admin_panel.py",
    "interfaces/gui/student_union_gui/analytics/analytics.py",
    "interfaces/gui/student_union_gui/book_clubs/book_clubs.py",
    "interfaces/gui/student_union_gui/clubs/club_actions.py",
    "interfaces/gui/student_union_gui/clubs/club_dialogs.py",
    "interfaces/gui/student_union_gui/clubs/club_discussions.py",
    "interfaces/gui/student_union_gui/clubs/club_finance.py",
    "interfaces/gui/student_union_gui/clubs/club_members.py",
    "interfaces/gui/student_union_gui/clubs/club_views.py",
    "interfaces/gui/student_union_gui/competitions/competition_admin.py",
    "interfaces/gui/student_union_gui/competitions/competition_registration.py",
    "interfaces/gui/student_union_gui/competitions/competition_results.py",
    "interfaces/gui/student_union_gui/competitions/competition_views.py",
    "interfaces/gui/student_union_gui/competitions/interclub_competitions.py",
    "interfaces/gui/student_union_gui/conferences/conferences.py",
    "interfaces/gui/student_union_gui/core/dashboard.py",
    "interfaces/gui/student_union_gui/core/main_gui.py",
    "interfaces/gui/student_union_gui/core/navigation.py",
    "interfaces/gui/student_union_gui/core/profile.py",
    "interfaces/gui/student_union_gui/core/utilities.py",
    "interfaces/gui/student_union_gui/elections/election_accessibility.py",
    "interfaces/gui/student_union_gui/elections/election_campaigns.py",
    "interfaces/gui/student_union_gui/elections/election_compliance.py",
    "interfaces/gui/student_union_gui/elections/election_core.py",
    "interfaces/gui/student_union_gui/elections/election_setup.py",
    "interfaces/gui/student_union_gui/elections/election_voting_methods.py",
    "interfaces/gui/student_union_gui/email/notifications.py",
    "interfaces/gui/student_union_gui/equipment/equipment_admin.py",
    "interfaces/gui/student_union_gui/equipment/equipment_browse.py",
    "interfaces/gui/student_union_gui/equipment/equipment_checkout.py",
    "interfaces/gui/student_union_gui/events/event_actions.py",
    "interfaces/gui/student_union_gui/events/event_dialogs.py",
    "interfaces/gui/student_union_gui/events/event_finance.py",
    "interfaces/gui/student_union_gui/events/event_recurring.py",
    "interfaces/gui/student_union_gui/events/event_ticketing.py",
    "interfaces/gui/student_union_gui/events/event_views.py",
    "interfaces/gui/student_union_gui/events/event_virtual.py",
    "interfaces/gui/student_union_gui/facilities/facility_booking.py",
    "interfaces/gui/student_union_gui/finance/expenses.py",
    "interfaces/gui/student_union_gui/gamification/rewards.py",
    "interfaces/gui/student_union_gui/green/green_initiatives_shared.py",
    "interfaces/gui/student_union_gui/integrations/external_integrations.py",
    "interfaces/gui/student_union_gui/knowledge/knowledge_sharing.py",
    "interfaces/gui/student_union_gui/mentorship/mentorship.py",
    "interfaces/gui/student_union_gui/misc.py",
    "interfaces/gui/student_union_gui/payments/payment_processing.py",
    "interfaces/gui/student_union_gui/streaming/live_streaming.py",
    "interfaces/gui/student_union_gui/support/peer_support.py",
    "interfaces/gui/student_union_gui/support/support_groups.py",
    "interfaces/gui/student_union_gui/support/wellness.py",
    "interfaces/gui/student_union_gui/volunteer/volunteer.py",
}

#: Domain packages that import this slice's own CLI or GUI adapter, usually to
#: re-export a launcher from ``__init__``. The dependency points outward.
_DOMAIN_IMPORTS_OWN_ADAPTER = {
    ("domain/health/dentist/integrations/email.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/appointments.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/notifications.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/patients.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/payments.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/prescriptions.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/refunds.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/reports.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/dentist/services/treatments.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.health.health_portal.dentist"),
    ("domain/health/portal/health_portal_core.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.wellbeing.wellness.wellness_cli"),
    ("domain/health/reporting/appointments.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.health_portal.reports.appointment_utilisation"),
    ("domain/health/reporting/conditions.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.health_portal.reports.condition_prevalence"),
    ("domain/health/reporting/population.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.health_portal.reports.population"),
    ("domain/health/reporting/vaccinations.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.health_portal.reports.vaccination"),
    ("domain/health/services/health_portal.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.health_portal"),
    ("domain/services/career_services/career_services_core.py",
     f"{_UNI}.domains.pastoral.interfaces.gui.career_services.career_services_gui"),
    ("domain/student_jobs/__init__.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_jobs.jobs_cli"),
    ("domain/student_life/student_union/events/application/analytics.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.analytics"),
    ("domain/student_life/student_union/events/application/attendance.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.attendance"),
    ("domain/student_life/student_union/events/application/event_catalogue.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.catalogue"),
    ("domain/student_life/student_union/events/application/finances.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.finances"),
    ("domain/student_life/student_union/events/application/knowledge_sharing.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.knowledge_sharing"),
    ("domain/student_life/student_union/events/application/recurring_events.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.recurring"),
    ("domain/student_life/student_union/events/application/registrations.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.registrations"),
    ("domain/student_life/student_union/events/application/sustainable_events.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.sustainability"),
    ("domain/student_life/student_union/events/application/ticketing.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.ticketing"),
    ("domain/student_life/student_union/events/application/virtual_events.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.virtual"),
    ("domain/student_life/student_union/events/event_management.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events"),
    ("domain/student_life/student_union/events/infrastructure/qr_codes.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.context"),
    ("domain/student_life/student_union/events/reporting/event_analytics.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.analytics"),
    ("domain/student_life/student_union/events/reporting/financial_report.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.student_union_events.context"),
    ("domain/wellbeing/wellness/__init__.py",
     f"{_UNI}.domains.pastoral.interfaces.cli.wellbeing.wellness.wellness_cli"),
}

#: Tk applications sitting in the domain layer.
_TKINTER_IN_DOMAIN = {
    "domain/health/dentist/services/appointments.py",
    "domain/health/dentist/services/notifications.py",
    "domain/health/dentist/services/patients.py",
    "domain/health/dentist/services/payments.py",
    "domain/health/dentist/services/prescriptions.py",
    "domain/health/dentist/services/refunds.py",
    "domain/health/dentist/services/reports.py",
    "domain/health/dentist/services/treatments.py",
    "domain/health/first_aid/first_aid_portal_shared.py",
    "domain/services/early_warning/early_warning_core_parts/launch_early_warning_gui.py",
    "domain/services/early_warning/outcomes/intervention_outcomes_app.py",
    "domain/student_life/student_union/elections/election_gui_shared.py",
    "domain/student_life/student_union/services/mentoring_matching/mentoring_matching_app.py",
    "domain/student_life/student_union/student_council.py",
    "domain/wellbeing/student_wellbeing/intervention_support.py",
}

#: Direct SQL driver use in the domain layer.
_SQLITE_IN_DOMAIN = {
    "domain/equality_diversity/integrations.py",
    "domain/equality_diversity/reports_engine.py",
    "domain/equality_diversity/schema.py",
    "domain/health/first_aid/first_aid_portal_shared.py",
    "domain/health/first_aid/first_aid_service.py",
    "domain/student_life/student_union/elections/election_gui_shared.py",
    "domain/student_life/student_union/services/mentoring_matching/matching_service.py",
    "domain/student_life/student_union/student_council.py",
    "domain/wellbeing/student_wellbeing/intervention_support.py",
    "domain/wellbeing/student_wellbeing/services/wellbeing_service.py",
}

KNOWN_VIOLATIONS: set[tuple[str, str]] = (
    {(p, _FINANCE_INTEGRATION) for p in _FINANCE_INTEGRATION_CALLERS}
    | {(p, "tkinter") for p in _TKINTER_IN_DOMAIN}
    | {(p, "sqlite3") for p in _SQLITE_IN_DOMAIN}
    | _DOMAIN_IMPORTS_OWN_ADAPTER
    | {
        # Newly visible now Academics is a slice: pastoral tools open the
        # Academics exam and grade windows directly.
        ("interfaces/gui/accessibility_tools_gui.py",
         f"{_ACAD}.interfaces.gui.exam_management"),
        ("interfaces/gui/internship_management/eligibility.py",
         f"{_ACAD}.interfaces.gui.grade_tracking_management_gui"),
        # Other Finance reaches: the ledger directly, and one GUI import.
    ("domain/health/dentist/integrations/finance.py",
     f"{_FIN}.domain.ledger"),
    ("domain/health/dentist/services/appointments.py",
     f"{_FIN}.domain.ledger"),
    ("domain/health/dentist/services/notifications.py",
     f"{_FIN}.domain.ledger"),
    ("domain/health/dentist/services/payments.py",
     f"{_FIN}.domain.ledger"),
    ("interfaces/gui/internship_management/integrations.py",
     f"{_FIN}.interfaces.gui.finance"),
    ("interfaces/gui/student_union_gui/core/utilities.py",
     f"{_FIN}.interfaces.gui.finance"),
    ("interfaces/gui/student_union_gui/payments/payment_processing.py",
     f"{_FIN}.domain.ledger"),
        # Domains not yet migrated.
    ("domain/student_life/student_union/administration/admin_management.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/administration/finance_oversight.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/administration/student_union_core.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/clubs/club_management/_imports.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/elections/election_management.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/events/application/ports.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/facilities/facility_management.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/services/menu.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/services/union_context.py",
     f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
    ("domain/student_life/student_union/student_council.py",
     f"{_ACAD}.domain.services.academic_calendar"),
    ("interfaces/gui/health/medical_accommodation/_common.py",
     f"{_OPS}.domain.campus.housing.services.accommodation"),
    }
)

#: Newly visible now Operations is a slice: while it sat at
#: interfaces/gui/operations/ and domain/operations/, reaches into it matched
#: neither boundary rule. These open Operations windows or call its services.
_OPERATIONS_REACHES: set[tuple[str, str]] = {
    ("interfaces/gui/student_union_gui/core/utilities.py",
     f"{_OPS}.interfaces.gui.campus.mobility.trip_management_gui"),
    ("interfaces/gui/student_union_gui/integrations/external_integrations.py",
     f"{_OPS}.interfaces.gui.campus.mobility.trip_management_gui"),
}

KNOWN_VIOLATIONS |= _OPERATIONS_REACHES


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)


def test_health_layers_moved_with_the_slice() -> None:
    """application/health and infrastructure/health came across too."""
    from pathlib import Path

    uni = Path(__file__).resolve().parents[6] / "src/education_system/systems/university"
    for layer in ("application/health", "infrastructure/health"):
        assert (uni / "domains/pastoral" / layer).is_dir(), f"missing {layer}"
        assert not (uni / layer).exists(), f"{layer} still in the shared package"
