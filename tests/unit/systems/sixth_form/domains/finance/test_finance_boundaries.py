"""Import-boundary tests for the sixth form Finance vertical slice.

The rules live in ``tests/unit/systems/sixth_form/domains/conftest.py``; this
module supplies only what Finance currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "finance"

_SF = "education_system.systems.sixth_form"

#: Real findings, recorded rather than tolerated. Each is work left in this slice.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # Direct SQL driver in a domain module — should go through
    # sixth_form.infrastructure.database, as fee_rules/free_meals/bursary_payments
    # already do.
    ("domain/bursaries/bursaries.py", "sqlite3"),
    ("domain/census_ilr/census_ilr.py", "sqlite3"),
    ("domain/expense_claims/expense_claims.py", "sqlite3"),
    ("domain/fees/fees.py", "sqlite3"),
    ("domain/funding/funding.py", "sqlite3"),
    ("domain/receipts/receipts.py", "sqlite3"),
    ("domain/trips/trips.py", "sqlite3"),
    # Domain rules reaching into other sixth form areas still under the legacy
    # domain/ tree. Mostly learner lookups (students), staff names, attendance
    # for bursary conditions, qualifications/value-added/SEND for the ILR
    # return, catering top-ups and the access gate (user_management). Each
    # becomes a port when the owning area moves into domains/. Catering has
    # already moved (domains/operations/), so those two entries now cross
    # into another migrated slice.
    ("domain/bursaries/bursaries.py", f"{_SF}.domain.learners.students"),
    ("domain/bursaries/bursaries.py", f"{_SF}.domain.staff"),
    ("domain/bursaries/bursary_payments.py", f"{_SF}.domain.academics.attendance"),
    ("domain/bursaries/bursary_payments.py", f"{_SF}.domain.learners.students"),
    ("domain/census_ilr/funding_summary.py", f"{_SF}.domain.academics.qualifications"),
    ("domain/census_ilr/funding_summary.py", f"{_SF}.domain.learners.students"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.academics.attendance"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.academics.qualifications"),
    # The single ILR export reads the per-enrolment ILR records (learning
    # delivery, aim outcomes) it is built from.
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.admissions.enrolments"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.assessment.value_added"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.governance.user_management"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.learners.students"),
    ("domain/census_ilr/return_builder.py", f"{_SF}.domain.pastoral.send"),
    ("domain/census_ilr/return_validation.py", f"{_SF}.domain.academics.qualifications"),
    ("domain/fees/fee_rules.py", f"{_SF}.domain.governance.user_management"),
    ("domain/fees/fee_rules.py", f"{_SF}.domain.learners.students"),
    ("domain/fees/fees.py", f"{_SF}.domain.learners.students"),
    ("domain/finance_hub/finance_hub.py", f"{_SF}.domain.staff.departments"),
    ("domain/free_meals/free_meals.py", f"{_SF}.domain.learners.students"),
    ("domain/online_payments/online_payments.py", f"{_SF}.domain.governance.user_management"),
    ("domain/online_payments/online_payments.py", f"{_SF}.domain.learners.students"),
    ("domain/online_payments/online_payments.py", f"{_SF}.domains.operations.domain.catering"),
    ("domain/online_payments/online_payments.py", f"{_SF}.domain.operations.communications.parent_portal"),
    ("domain/receipts/receipts.py", f"{_SF}.domain.learners.students"),
    ("domain/trips/trips.py", f"{_SF}.domain.learners.students"),
    ("domain/trips/trips.py", f"{_SF}.domain.staff"),
    # Finance screens and menus reading other areas directly (student pickers,
    # staff/department lookups, the access gate) or borrowing another area's
    # UI helpers (operations/_ops_ui, compliance measures views).
    ("interfaces/cli/_prompts.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/bursaries/bursaries_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/bursaries/bursary_payments_cli.py", f"{_SF}.domain.academics.attendance"),
    ("interfaces/cli/bursaries/bursary_payments_cli.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/cli/bursaries/bursary_payments_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/census_ilr/return_builder_cli.py", f"{_SF}.domain.academics.attendance"),
    ("interfaces/cli/census_ilr/return_builder_cli.py", f"{_SF}.interfaces.cli.governance.compliance.measures"),
    ("interfaces/cli/fees/fee_rules_cli.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/cli/fees/fees_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/free_meals/free_meals_cli.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/cli/online_payments/online_payments_cli.py", f"{_SF}.interfaces.cli.operations._ops_cli"),
    ("interfaces/cli/receipts/receipts_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/trips/trip_refunds_cli.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/cli/trips/trip_refunds_cli.py", f"{_SF}.domain.staff.departments"),
    ("interfaces/cli/trips/trips_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/_widgets.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/gui/_widgets.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/bursaries/bursaries_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/bursaries/bursaries_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/bursaries/bursary_payments_views.py", f"{_SF}.domain.academics.attendance"),
    ("interfaces/gui/bursaries/bursary_payments_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/census_ilr/return_builder_views.py", f"{_SF}.domain.academics.attendance"),
    ("interfaces/gui/census_ilr/return_builder_views.py", f"{_SF}.interfaces.gui.governance.compliance.measures.measures_views"),
    ("interfaces/gui/fees/fee_rules_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/fees/fees_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/free_meals/free_meals_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/online_payments/online_payments_views.py", f"{_SF}.interfaces.gui.operations._ops_ui"),
    ("interfaces/gui/online_payments/pay_dialog.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/gui/online_payments/pay_dialog.py", f"{_SF}.domains.operations.domain.catering"),
    ("interfaces/gui/receipts/receipts_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/trips/trip_refunds_views.py", f"{_SF}.domain.staff.departments"),
    ("interfaces/gui/trips/trips_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/trips/trips_views.py", f"{_SF}.domain.staff"),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
