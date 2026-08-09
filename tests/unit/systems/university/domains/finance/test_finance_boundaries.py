"""Import-boundary tests for the Finance vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Finance currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "finance"

_UNI = "education_system.systems.university"
_PAS = f"{_UNI}.domains.pastoral"
_ACAD = f"{_UNI}.domains.academics"

#: Ten domain modules import Flask directly. The document is explicit that the
#: domain layer carries "business rules; no GUI, Flask or SQL imports" — these
#: are request-scoped helpers and small embedded apps that belong in
#: interfaces/api or interfaces/web. This is the largest single cluster of
#: boundary work in the slice.
_FLASK_IN_DOMAIN = {
    "domain/billing/fee_structure.py",
    "domain/billing/payment_plans.py",
    "domain/core/account_management.py",
    "domain/core/finance_context.py",
    "domain/core/financial_core.py",
    "domain/core/security_automation.py",
    "domain/core/students.py",
    "domain/reporting/budget_analysis.py",
    "domain/reporting/revenue_analytics/app.py",
    "domain/scholarships/scholarship_programs.py",
}

KNOWN_VIOLATIONS: set[tuple[str, str]] = {(path, "flask") for path in _FLASK_IN_DOMAIN} | {
    # A standalone Tk launcher living in the domain layer. It belongs in
    # interfaces/gui/ alongside the other bursary UI.
    ("domain/bursary/bursary_app.py", "tkinter"),
    # Two domain packages re-export their CLI adapter from __init__, so importing
    # the business rules drags the interface in. The dependency points outward.
    (
        "domain/budget/__init__.py",
        f"{_UNI}.domains.finance.interfaces.cli.budget.budget_cli",
    ),
    (
        "domain/scholarship_finder/__init__.py",
        f"{_UNI}.domains.finance.interfaces.cli.scholarship_finder.scholarship_cli",
    ),
    # Newly visible now Pastoral is a slice: this opens Pastoral's student-app
    # documentation window directly.
    (
        "interfaces/gui/finance/finance_gui.py",
        f"{_PAS}.interfaces.gui.student_app.documentation.documentation_gui",
    ),
    # Newly visible now Academics is a slice: the finance layout opens the
    # research-grants window directly.
    ("interfaces/gui/finance/layout/_base.py",
     f"{_ACAD}.interfaces.gui.research.research_grants_gui"),
    ("interfaces/gui/finance/layout/_research_grants.py",
     f"{_ACAD}.interfaces.gui.research.research_grants_gui"),
    # Payment recording reads Governance's international-compliance service
    # directly. Both are slices now, so this is an explicit cross-slice call
    # that wants a query port on Governance.
    (
        "interfaces/gui/finance/transaction_manager/payment_recording.py",
        f"{_UNI}.domains.governance.domain.compliance.international_compliance.services",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
