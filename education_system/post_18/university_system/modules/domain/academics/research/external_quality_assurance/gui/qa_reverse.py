"""Reverse drill-throughs — actions other GUIs invoke to push state
*into* EQA. Each helper performs the side effect via ``qa_service``
then opens (or focuses) the EQA dashboard at the relevant tab.
"""

from __future__ import annotations

import logging
from typing import Optional

from education_system.post_18.university_system.modules.domain.academics.research.external_quality_assurance.services import (
    qa_service as qa,
)

logger = logging.getLogger(__name__)


def _ensure_dashboard(app) -> Optional[object]:
    """Open the EQA dashboard if not already, return the live instance."""
    dash = getattr(app, "_eqa_dash", None)
    if dash is not None:
        try:
            if dash.window.winfo_exists():
                dash.window.lift()
                return dash
        except Exception:
            pass
    fn = getattr(app, "show_qa_dashboard_gui", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            logger.exception("could not open EQA dashboard")
    return getattr(app, "_eqa_dash", None)


def snapshot_cohort_to_b3(app, cohort_year: int,
                           course: Optional[str] = None) -> int:
    """#7 — Snapshot the given cohort to B3, then focus the EQA OfS tab
    at that year."""
    n = qa.record_b3_snapshot(cohort_year, course=course)
    dash = _ensure_dashboard(app)
    if dash is not None:
        try:
            dash.set_focus(framework="OfS", year=cohort_year)
        except Exception:
            pass
    return n


def send_output_to_impact_case(app, output_id: int, case_id: int) -> bool:
    """#8 — Attach a research output to a REF impact case, then focus
    the REF tab on the case's UoA."""
    ok = qa.add_output_to_impact_case(output_id, case_id)
    if ok:
        dash = _ensure_dashboard(app)
        try:
            if dash is not None:
                cases = qa.list_impact_cases()
                uoa = next((c["uoa"] for c in cases
                            if c["id"] == case_id), None)
                if uoa:
                    dash.set_focus(framework="REF", uoa=uoa)
        except Exception:
            pass
    return ok


def promote_alert_to_milestone(app, alert: dict) -> int:
    """#9 — Promote a Predictive Alerts dict into an APP milestone."""
    mid = qa.promote_alert_to_app_milestone(alert)
    dash = _ensure_dashboard(app)
    if dash is not None:
        try:
            dash.set_focus(framework="OfS")
        except Exception:
            pass
    return mid


def link_hesa_return_to_qa(app, qa_id: int, hesa_return_id: int) -> bool:
    """#10 — Persist a HESA↔OfS submission link."""
    return qa.link_qa_submission_to_hesa(qa_id, hesa_return_id)


def recompute_eqa_kpis(app) -> int:
    """#11 — Force-recompute all EQA KPIs (callable from BI / admin)."""
    return qa.record_external_qa_kpis()


__all__ = [
    "snapshot_cohort_to_b3", "send_output_to_impact_case",
    "promote_alert_to_milestone", "link_hesa_return_to_qa",
    "recompute_eqa_kpis",
]
