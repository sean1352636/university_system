"""Import-boundary tests for the sixth form Operations vertical slice.

The rules live in ``tests/unit/systems/sixth_form/domains/conftest.py``; this
module supplies only what Operations currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "operations"

_SF = "education_system.systems.sixth_form"

#: Real findings, recorded rather than tolerated. Each is work left in this slice.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # Direct SQL driver in a domain module — should go through
    # sixth_form.infrastructure.database, as lockers/parking/catering already do.
    ("domain/assets/assets.py", "sqlite3"),
    ("domain/health_safety/health_safety.py", "sqlite3"),
    ("domain/transport/transport.py", "sqlite3"),
    ("domain/visitors/visitors.py", "sqlite3"),
    # Domain rules reaching into other sixth form areas still under the legacy
    # domain/ tree: learner lookups (students), staff names, the access gate
    # (user_management), the IT acceptable-use policy (policies), dietary
    # needs (medical_records), fire-drill registers (attendance) and room
    # lookups for helpdesk tickets (room_booking). Each becomes a port when
    # the owning area moves into domains/.
    ("domain/assets/assets.py", f"{_SF}.domain.staff"),
    ("domain/catering/biometric_consent.py", f"{_SF}.domain.governance.user_management"),
    ("domain/catering/biometric_consent.py", f"{_SF}.domain.learners.students"),
    ("domain/catering/cashless.py", f"{_SF}.domain.governance.user_management"),
    ("domain/catering/cashless.py", f"{_SF}.domain.learners.students"),
    ("domain/catering/catering.py", f"{_SF}.domain.governance.user_management"),
    ("domain/catering/catering.py", f"{_SF}.domain.learners.students"),
    ("domain/catering/catering.py", f"{_SF}.domain.pastoral.health.medical_records"),
    ("domain/device_loans/acceptable_use.py", f"{_SF}.domain.governance.policies"),
    ("domain/device_loans/acceptable_use.py", f"{_SF}.domain.governance.user_management"),
    ("domain/device_loans/acceptable_use.py", f"{_SF}.domain.learners.students"),
    ("domain/device_loans/acceptable_use.py", f"{_SF}.domain.staff"),
    ("domain/device_loans/device_loans.py", f"{_SF}.domain.governance.user_management"),
    ("domain/device_loans/device_loans.py", f"{_SF}.domain.learners.students"),
    ("domain/device_loans/device_loans.py", f"{_SF}.domain.staff"),
    ("domain/health_safety/health_safety.py", f"{_SF}.domain.learners.students"),
    ("domain/health_safety/health_safety.py", f"{_SF}.domain.staff"),
    ("domain/health_safety/premises_checks.py", f"{_SF}.domain.academics.attendance"),
    ("domain/health_safety/premises_checks.py", f"{_SF}.domain.governance.user_management"),
    ("domain/helpdesk/helpdesk.py", f"{_SF}.domain.academics.room_booking"),
    ("domain/helpdesk/helpdesk.py", f"{_SF}.domain.governance.user_management"),
    ("domain/helpdesk/helpdesk.py", f"{_SF}.domain.staff"),
    ("domain/id_cards/id_cards.py", f"{_SF}.domain.learners.students"),
    ("domain/id_cards/id_cards.py", f"{_SF}.domain.staff"),
    ("domain/lockers/lockers.py", f"{_SF}.domain.learners.students"),
    ("domain/parking/parking.py", f"{_SF}.domain.learners.students"),
    ("domain/parking/parking.py", f"{_SF}.domain.staff"),
    ("domain/visitors/visitors.py", f"{_SF}.domain.governance.user_management"),
    # Domain rules reaching into the already-migrated Finance slice: cashless
    # top-ups post to online payments / receipts and apply free-meal and
    # bursary allowances; device loans link to bursary applications. The reverse
    # direction (finance -> catering) is pinned in the Finance test.
    ("domain/catering/cashless.py", f"{_SF}.domains.finance.domain.bursaries"),
    ("domain/catering/cashless.py", f"{_SF}.domains.finance.domain.free_meals"),
    ("domain/catering/cashless.py", f"{_SF}.domains.finance.domain.online_payments"),
    ("domain/catering/cashless.py", f"{_SF}.domains.finance.domain.receipts"),
    ("domain/device_loans/device_loans.py", f"{_SF}.domains.finance.domain.bursaries"),
    # Operations screens and menus reading other areas directly (student and
    # staff pickers, the access gate, the acceptable-use policy) or borrowing
    # UI helpers that sit deeper than the shared interfaces/{gui,cli}/_*.py:
    # operations/_ops_ui and _ops_cli (shared with Finance and others, left in
    # the system-wide tree until they move to a shell) and progression's
    # _record_tabs.
    ("interfaces/cli/assets/assets_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/cli/catering/cashless_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/catering/catering_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/device_loans/device_loans_cli.py", f"{_SF}.domain.governance.policies"),
    ("interfaces/cli/device_loans/device_loans_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/health_safety/health_safety_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/health_safety/health_safety_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/cli/health_safety/premises_checks_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/helpdesk/helpdesk_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/id_cards/id_cards_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/lockers/lockers_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/parking/parking_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/transport/transport_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/visitors/visitors_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/assets/assets_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/catering/cashless_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/catering/cashless_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/catering/catering_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/device_loans/device_loans_views.py", f"{_SF}.domain.governance.policies"),
    ("interfaces/gui/device_loans/device_loans_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/health_safety/health_safety_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/health_safety/health_safety_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/health_safety/premises_checks_views.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/gui/health_safety/premises_checks_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/health_safety/premises_checks_views.py", f"{_SF}.interfaces.gui.progression"),
    ("interfaces/gui/helpdesk/helpdesk_views.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/gui/helpdesk/helpdesk_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/helpdesk/helpdesk_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/helpdesk/helpdesk_views.py", f"{_SF}.interfaces.gui.progression"),
    ("interfaces/gui/id_cards/id_cards_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/lockers/lockers_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/parking/parking_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/transport/transport_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/visitors/visitors_views.py", f"{_SF}.domain.staff"),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
