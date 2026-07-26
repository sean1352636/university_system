"""Lightweight integration helpers for other GUIs to consult MC state.

Each helper is best-effort: callers are GUIs that should not crash if the
service is unavailable or the tables are empty. All functions return
plain dicts/lists or ``None`` so they can be embedded directly in row
formatting and tooltip text.
"""

from typing import Dict, List, Optional


def _service():
    try:
        from education_system.systems.university.domain.assessment.mitigating_circumstances.services.mitigating_circumstances_service import (
            MitigatingCircumstancesService,
        )
        return MitigatingCircumstancesService()
    except Exception:
        return None


def get_active_extension(student_id: str, module_code: str,
                         assessment_ref: str) -> Optional[Dict]:
    """Return the most recent MC-driven extension for an assessment, or None."""
    svc = _service()
    if not svc or not (student_id and module_code and assessment_ref):
        return None
    try:
        return svc.get_active_extension(student_id, module_code, assessment_ref)
    except Exception:
        return None


def claims_for_student(student_id: str, statuses: tuple = None) -> List[Dict]:
    """All claims for a student, optionally filtered by a tuple of statuses."""
    svc = _service()
    if not svc or not student_id:
        return []
    try:
        rows = svc.list_claims(student_id=student_id)
    except Exception:
        return []
    if statuses:
        rows = [r for r in rows if r.get('status') in statuses]
    return rows


def has_open_claim_for_assessment(student_id: str, module_code: str,
                                  assessment_ref: str) -> bool:
    """True if the student has any non-terminal claim against this assessment."""
    open_states = ('submitted', 'evidence_pending', 'under_review', 'panel_scheduled')
    for c in claims_for_student(student_id, statuses=open_states):
        if (c.get('module_code') == module_code
                and c.get('assessment_ref') == assessment_ref):
            return True
    return False


def deferred_assessments_for_student(student_id: str) -> List[Dict]:
    """Claims with a deferral outcome — for Exam Management to schedule next sitting."""
    svc = _service()
    if not svc or not student_id:
        return []
    try:
        with __import__(
            'education_system.systems.university.infrastructure.database.db',
            fromlist=['get_connection']
        ).get_connection() as conn:
            rows = conn.execute(
                """SELECT c.id AS claim_id, c.student_id, c.module_code,
                          c.assessment_ref, pi.outcome, pi.decided_at
                   FROM mc_claims c
                   JOIN mc_panel_items pi ON pi.claim_id = c.id
                   WHERE c.student_id = ?
                     AND pi.outcome IN ('deferral_granted','uncapped_resit','capped_resit')
                   ORDER BY pi.decided_at DESC""",
                (student_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def aggregate_stats() -> Dict:
    """Roll-up MC stats for the External QA dashboard."""
    svc = _service()
    if not svc:
        return {'total_claims': 0, 'by_status': {}, 'by_grounds': {},
                'extensions_granted': 0, 'approval_rate': 0.0}
    try:
        stats = svc.claim_statistics()
    except Exception:
        return {'total_claims': 0, 'by_status': {}, 'by_grounds': {},
                'extensions_granted': 0, 'approval_rate': 0.0}
    total = stats.get('total_claims') or 0
    approved = (stats.get('by_status') or {}).get('approved', 0)
    rejected = (stats.get('by_status') or {}).get('rejected', 0)
    decided = approved + rejected
    stats['approval_rate'] = round(approved / decided, 3) if decided else 0.0
    return stats


def open_mc_gui_for_student(parent, student_id: str = None) -> bool:
    """Open the MC GUI; if a student_id is given, prefill the evidence tab.

    Returns True on success. Failures are swallowed (callers are GUIs)."""
    try:
        from education_system.systems.university.interfaces.gui.assessment.mitigating_circumstances.mitigating_circumstances_gui import (
            MitigatingCircumstancesGUI,
        )
    except Exception:
        return False
    try:
        gui = MitigatingCircumstancesGUI(parent=parent)
        if student_id and hasattr(gui, 'claims_tree'):
            # Best-effort highlight: select first row matching student_id.
            for iid in gui.claims_tree.get_children():
                vals = gui.claims_tree.item(iid).get('values') or []
                if len(vals) >= 2 and str(vals[1]) == str(student_id):
                    gui.claims_tree.selection_set(iid)
                    gui.claims_tree.see(iid)
                    break
        return True
    except Exception:
        return False
