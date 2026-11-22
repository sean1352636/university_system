"""Import-boundary tests for the Operations vertical slice.

The last of the eleven university domains. The rules live in
``tests/unit/systems/university/domains/conftest.py``; this module supplies only
what Operations currently violates. The allow-list is a ratchet, so it can only
shrink.

159 entries across 802 modules — 19.8 per cent. One cluster is almost the whole
story: 118 modules import Finance's integration module, because every commercial
outlet (barber, betting, butcher, cafe, car rental, cinema, gym, marketplace,
music shop, nail bar, phone shop, restaurant, textbooks) takes payment by calling
Finance directly.

Together with Pastoral's 56 and the Academics cluster, "post to Finance by
import" is the single largest structural debt this migration surfaced, and one
published charge-raised event would retire the lot.
"""

from __future__ import annotations

SLICE = "operations"

_UNI = "education_system.systems.university"
_FIN = f"{_UNI}.domains.finance"

#: Every commercial outlet posts payments through Finance's integration module.
_FINANCE_INTEGRATION = f"{_FIN}.infrastructure.finance_integration"

_FINANCE_INTEGRATION_CALLERS = {
    "domain/campus/housing/services/housing_accommodation/common.py",
    "interfaces/gui/campus/equipment/equipment_gui.py",
    "interfaces/gui/campus/mobility/parking_management/dialogs/payment_dialog.py",
    "interfaces/gui/campus/mobility/parking_management/dialogs/refund_dialog.py",
    "interfaces/gui/campus/mobility/taxi_booking_gui_shared.py",
    "interfaces/gui/campus/mobility/train_station_gui_shared.py",
    "interfaces/gui/campus/printing/printing_gui.py",
}

#: Tk applications sitting in the domain layer.
_TKINTER_IN_DOMAIN = {
    "domain/campus/mobility/services/parking_launcher.py",
    "domain/campus/services/campus_events_gui.py",
    "domain/communications/feedback/complaints_portal.py",
    "domain/reporting/institutional_analytics/institutional_analytics_app.py",
    "domain/reporting/kpi_dashboard/kpi_dashboard_app.py",
}

#: Direct SQL driver use in the domain layer.
_SQLITE_IN_DOMAIN = {
    "domain/campus/housing/services/housing_accommodation/extended_cli.py",
    "domain/campus/housing/services/housing_accommodation/extras.py",
    "domain/campus/housing/services/housing_accommodation/waitlist.py",
    "domain/campus/room_booking/services/room_booking_service.py",
    "domain/communications/feedback/complaints_portal.py",
    "domain/reporting/institutional_analytics/services/institutional_analytics_service.py",
    "domain/reporting/kpi_dashboard/services/kpi_dashboard_service.py",
}

KNOWN_VIOLATIONS: set[tuple[str, str]] = (
    {(p, _FINANCE_INTEGRATION) for p in _FINANCE_INTEGRATION_CALLERS}
    | {(p, "tkinter") for p in _TKINTER_IN_DOMAIN}
    | {(p, "sqlite3") for p in _SQLITE_IN_DOMAIN}
    | {
        # Everything else: other Finance reaches, Academics, this slice's own
        # adapters, tkinter submodules, and two singletons.
        #
        # The bakery entry is a *dangling* import, not merely a boundary
        # crossing: `university.domain.helpdesk` has never existed — the helpdesk
        # service has always lived under pastoral/services/helpdesk (now
        # domains/student_support/domain/helpdesk), and it is substantial. The
        # import sits in a try/except, so the bakery's "raise a helpdesk ticket"
        # path silently does nothing. Repointing the path is not sufficient
        # either: that package exposes create_ticket_enhanced(auth) and
        # create_ticket_from_template(auth, template_id), not the create_ticket()
        # this calls. Wiring it up needs a decision about what the bakery passes
        # for `auth`, so it is recorded here rather than guessed at.
        ("domain/campus/campus_navigation/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.campus_navigation.navigation_cli"),
        ("domain/campus/facilities/services/facilities_management_core.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.facilities.facilities_cli"),
        ("domain/campus/facilities/services/facilities_management_core.py",
         f"{_UNI}.domains.operations.interfaces.gui.campus.facilities.building_management_app"),
        ("domain/campus/housing/services/housing_accommodation/deposits.py",
         f"{_FIN}.domain.ledger"),
        ("domain/campus/housing/services/housing_accommodation/deposits.py",
         f"{_FIN}.domain.ledger.hooks"),
        ("domain/campus/housing/services/housing_accommodation/payments.py",
         f"{_FIN}.domain.ledger"),
        ("domain/campus/lost_found/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.lost_found.lost_found_cli"),
        ("domain/campus/mobility/services/parking_launcher.py",
         f"{_UNI}.domains.operations.interfaces.gui.campus.mobility.parking_management_gui"),
        ("domain/campus/mobility/services/parking_launcher.py",
         "tkinter.ttk"),
        ("domain/reporting/external_qa_kpis.py",
         f"{_UNI}.domains.quality.domain.external_quality_assurance.services"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/finance_integration.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/finance_integration.py",
         f"{_FIN}.interfaces.gui.finance.finance_gui"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.domain.core.account_management"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.interfaces.gui.finance.finance_gui"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/refund_manager.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/trip_management_gui/_imports.py",
         f"{_UNI}.domains.teaching.domain.academic_calendar.calendar_core"),
        ("interfaces/gui/campus/mobility/trip_management_gui/_imports.py",
         f"{_UNI}.domains.teaching.domain.academic_calendar.config"),
        ("interfaces/gui/communications/mail/mail_post_gui.py",
         f"{_FIN}.domain.core.finance_db_operations"),
    }
)


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)


def test_legacy_domain_tree_is_empty() -> None:
    """All eleven domains have migrated: domain/ holds no modules."""
    from pathlib import Path

    legacy = (
        Path(__file__).resolve().parents[6]
        / "src/education_system/systems/university/domain"
    )
    leftover = sorted(p.name for p in legacy.rglob("*.py") if p.name != "__init__.py")
    assert not leftover, f"modules still in the legacy domain/ tree: {leftover}"
