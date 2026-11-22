"""Ports Student Support uses to reach other university domains.

Student Support lives in the Pastoral slice and may not import another domain
directly (the slice boundary ratchet), so what a support ticket hands on goes
through here:

* ``raise_safeguarding_concern(subject, content, ...)`` — a CRITICAL concern in
  the safeguarding register (``safeguarding.application.services.submissions``),
  the same way the chatbot raises one for crisis language; returns its id;
* ``safeguarding_lead_roles()`` — the roles that work safeguarding cases (the
  designated safeguarding leads: every role the safeguarding permissions let
  close a case, admins excepted);
* ``submit_mitigating_claim(...)`` — a mitigating circumstances claim
  (Assessment: ``MitigatingCircumstancesService.submit_claim``);
  ``mitigating_grounds()`` — the grounds it accepts;
* ``hardship_funds()`` / ``submit_hardship_application(...)`` — open hardship
  funds and an application to one (Finance: ``BursaryService``);
* ``accommodation_types()`` / ``submit_accommodation_request(...)`` — a
  reasonable-adjustments request to accessibility services (Operations:
  ``AccessibilityService``), which also queues it for the health portal's
  approval.

Each call opens its own connection and commits there: callers must not hold a
write transaction on the university database while calling.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── safeguarding ────────────────────────────────────────────────────────

def safeguarding_lead_roles() -> frozenset:
    """Roles that work safeguarding cases (lower case, admins excluded)."""
    from education_system.systems.university.domains.safeguarding.domain import permissions
    roles = getattr(permissions, "_ROLE_PERMISSIONS", {})
    return frozenset(role for role, perms in roles.items()
                     if "close" in perms and "*" not in perms)


def raise_safeguarding_concern(subject: dict, content: str, *, snippet: str = "",
                               reporter_username: Optional[str] = None) -> int:
    """Raise a CRITICAL self-harm / mental-health concern about ``subject``
    (``{'username', 'full_name', 'role'}``); returns the concern's id.
    ``reporter_username`` is set when someone else raised it on their behalf."""
    from education_system.systems.university.domains.safeguarding.application.services import (
        submissions,
    )
    from education_system.systems.university.domains.safeguarding.domain.analysis import (
        RiskCategory,
    )
    # Categories map a category to the text that raised it (as the
    # safeguarding wizard records them); self-harm triggers mandatory
    # reporting to the safeguarding lead.
    categories = {RiskCategory.SELF_HARM: [snippet[:300]], RiskCategory.MENTAL_HEALTH: []}
    on_behalf = bool(reporter_username and reporter_username != subject.get("username"))
    return int(submissions.save_submission(
        subject, content, "CRITICAL", categories, consent_contact=True,
        on_behalf_of=on_behalf, reporter_username=reporter_username if on_behalf else None))


# ── mitigating circumstances ────────────────────────────────────────────

def mitigating_grounds() -> tuple:
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.services.mitigating_circumstances_service import (
        VALID_GROUNDS,
    )
    return tuple(VALID_GROUNDS)


def submit_mitigating_claim(student_id: str, *, grounds: str, description: str,
                            submitted_by: str, module_code: Optional[str] = None,
                            assessment_ref: Optional[str] = None,
                            period_start: Optional[str] = None,
                            period_end: Optional[str] = None,
                            impact_statement: Optional[str] = None,
                            requested_remedy: Optional[str] = None) -> int:
    """A new mitigating circumstances claim (status ``submitted``); its id."""
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.services.mitigating_circumstances_service import (
        MitigatingCircumstancesService,
    )
    return int(MitigatingCircumstancesService().submit_claim(
        student_id=student_id, module_code=module_code, assessment_ref=assessment_ref,
        grounds=grounds, description=description, period_start=period_start,
        period_end=period_end, impact_statement=impact_statement,
        requested_remedy=requested_remedy, submitted_by=submitted_by))


# ── hardship ────────────────────────────────────────────────────────────

def _bursary():
    from education_system.systems.university.domains.finance.domain.bursary.services.bursary_service import (
        BursaryService,
    )
    return BursaryService()


def hardship_funds() -> list[dict]:
    """Open hardship and emergency funds (``fund_id``, ``name``, ...)."""
    service = _bursary()
    funds = []
    for fund_type in ("hardship", "emergency"):
        funds += service.list_funds(fund_type=fund_type, status="open")
    return funds


def submit_hardship_application(student_id: str, fund_id: int, requested_amount: float, *,
                                circumstances: str,
                                household_income: Optional[float] = None) -> int:
    """A hardship fund application (status ``submitted``); its id. Raises
    ``ValueError`` with the fund's own message when it is refused."""
    from education_system.systems.university.domains.finance.domain.bursary.services.bursary_service import (
        BursaryError,
    )
    try:
        return int(_bursary().submit_application(
            student_id, int(fund_id), float(requested_amount),
            household_income=household_income, circumstances=circumstances))
    except BursaryError as exc:
        raise ValueError(str(exc)) from None


# ── reasonable adjustments ──────────────────────────────────────────────

def _accessibility():
    from education_system.systems.university.domains.student_support.domain.disability.accessibility_service import (
        AccessibilityService,
    )
    return AccessibilityService()


def accommodation_types() -> tuple:
    from education_system.systems.university.domains.student_support.domain.disability.accessibility_service import (
        AccessibilityService,
    )
    return tuple(AccessibilityService.ACCOMMODATION_TYPES)


def submit_accommodation_request(student_id: str, *, student_name: str, student_email: str,
                                 accommodation_type: str, description: str) -> int:
    """A reasonable-adjustments request to accessibility services; its id."""
    return int(_accessibility().submit_accommodation_request(
        student_id, student_name, student_email, accommodation_type, description))


__all__: list[Any] = [
    "safeguarding_lead_roles", "raise_safeguarding_concern",
    "mitigating_grounds", "submit_mitigating_claim",
    "hardship_funds", "submit_hardship_application",
    "accommodation_types", "submit_accommodation_request",
]
