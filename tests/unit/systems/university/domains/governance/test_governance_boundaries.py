"""Import-boundary tests for the Governance vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Governance currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "governance"

_UNI = "education_system.systems.university"
_PAS = f"{_UNI}.domains.pastoral"
_FIN = f"{_UNI}.domains.finance"
_ACAD = f"{_UNI}.domains.academics"

#: Direct SQL driver use in the domain layer. These modules predate the
#: repository / unit-of-work pattern the modernised core uses.
_SQLITE_IN_DOMAIN = {
    "domain/health_safety/health_safety_portal.py",
    "domain/health_safety/health_safety_service.py",
    "domain/legal/disciplinary/_db_init.py",
    "domain/legal/disciplinary/disciplinary_portal.py",
    "domain/legal/disciplinary/fitness_to_practise/_db_init.py",
    "domain/legal/disciplinary/fitness_to_practise/services/ftp_service.py",
    "domain/legal/information_rights/services/information_rights_core.py",
    "domain/legal/risk_management/risk_service.py",
}

#: "Portal" modules in the domain layer that are really Tk applications.
_TKINTER_IN_DOMAIN = {
    "domain/health_safety/health_safety_portal.py",
    "domain/legal/disciplinary/disciplinary_portal.py",
    "domain/legal/disciplinary/fitness_to_practise/fitness_to_practise.py",
    "domain/legal/risk_management/university_risk_management.py",
}

KNOWN_VIOLATIONS: set[tuple[str, str]] = (
    {(p, "sqlite3") for p in _SQLITE_IN_DOMAIN}
    | {(p, "tkinter") for p in _TKINTER_IN_DOMAIN}
    | {
        # A domain module importing this slice's own GUI portal.
        (
            "domain/legal/disciplinary/fitness_to_practise/fitness_to_practise.py",
            f"{_UNI}.domains.governance.interfaces.gui.legal.disciplinary"
            ".fitness_to_practise.ftp_portal_gui",
        ),
        # Legal work posts charges and refunds straight into Finance's ledger.
        # Fines, settlements and refunds arising from disciplinary or legal
        # outcomes should be raised as events for Finance to post.
        ("domain/legal/services/legal_services_core.py", f"{_FIN}.domain.ledger"),
        ("interfaces/api/legal_routes.py", f"{_FIN}.domain.ledger"),
        ("interfaces/gui/legal/billing.py", f"{_FIN}.domain.ledger"),
        ("interfaces/gui/legal/refunds.py", f"{_FIN}.domain.ledger"),
        (
            "interfaces/gui/legal/refunds.py",
            f"{_FIN}.infrastructure.finance_integration",
        ),
        (
            "interfaces/gui/legal/_imports.py",
            f"{_FIN}.domain.core.finance_db_operations",
        ),
        # Newly visible now Pastoral is a slice: this opens Pastoral's student-app
        # documentation window directly.
        (
            "interfaces/gui/compliance/international_compliance/visa_compliance_gui.py",
            f"{_PAS}.interfaces.gui.student_app.documentation.documentation_gui",
        ),
        # Visa compliance reads Academics attendance directly — attendance is
        # evidence for a visa decision, so this wants a query port.
        (
            "domain/compliance/international_compliance/services/visa_service.py",
            f"{_ACAD}.domain.services.attendance.absence_tracking"
            ".absence_enhancements",
        ),
        # HESA export reads the Academics curriculum specification directly.
        (
            "interfaces/gui/compliance/hesa_export/hesa_export_gui.py",
            f"{_ACAD}.domain.curriculum_specification.services"
            ".curriculum_specification_service",
        ),
    }
)


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
