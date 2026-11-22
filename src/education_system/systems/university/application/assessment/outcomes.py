"""Assessment-domain facts that other slices need, behind one port.

Academics rolls assignment marks up into module results and offers resits;
both need answers the Assessment slice owns (the grade scale, and what a
mitigating-circumstances panel decided). Slices may not import each other, so
they ask here.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Panel outcomes that entitle a student to an uncapped sitting.
UNCAPPED_MC_OUTCOMES = ("deferral_granted", "uncapped_resit")


def percentage_to_letter(percentage: float) -> str | None:
    """The university's letter grade for a percentage, or None if unavailable."""
    try:
        from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.conversions import (
            percentage_to_letter as convert,
        )
    except Exception:
        logger.debug("Grade scale unavailable", exc_info=True)
        return None
    return convert(percentage)


def uncapped_resit_claim(student_id: str, module_code: str) -> int | None:
    """The MC claim that grants this student an uncapped sitting on the module, if any."""
    try:
        from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.integration import (
            deferred_assessments_for_student,
        )
    except Exception:
        logger.debug("Mitigating circumstances unavailable", exc_info=True)
        return None
    for claim in deferred_assessments_for_student(student_id):
        if claim.get("module_code") == module_code and claim.get("outcome") in UNCAPPED_MC_OUTCOMES:
            return claim.get("claim_id")
    return None


def appeal_uncapped_resit(student_id: str, module_code: str) -> int | None:
    """The academic appeal whose upheld outcome grants this student an uncapped
    resit on the module (``academic_appeal_actions``), if any."""
    try:
        from education_system.systems.university.application.cases import appeals
        return appeals.uncapped_resit_appeal(student_id, module_code)
    except Exception:
        logger.debug("Academic appeals unavailable", exc_info=True)
        return None
