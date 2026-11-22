"""Onboarding "Bursary applied for" ↔ the 16-19 bursary application.

The task is backed by the learner's bursary application (finance
bursaries domain, read through its public functions):

* ticking it needs a bursary application for the checklist's academic
  year that has gone past Draft (submitted, under review, decided …) —
  the task then keeps ``evidence_ref`` ``bursary:<application id>``;
* a Draft application (opened on conversion when the applicant said they
  wanted a bursary) does not count: the learner still has to apply;
* with no application at all, a *required* task asks for one (or written
  evidence) and an optional one ticks freely.

:func:`link_application` points a checklist's task at an application
(conversion calls it), :func:`sync_open_items` ticks every open task whose
application has since been submitted (for a scheduled job or a "Sync"
action).

The rule is registered with :func:`onboarding.register_evidence_rule` when
onboarding first checks evidence.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

BURSARY_KEY = "Bursary applied for"
REF_PREFIX = "bursary:"
#: Application statuses that do not show the learner applied.
_NOT_APPLIED = ("Draft", "Cancelled", "Withdrawn")


def _bursaries():
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    return bursaries


def _application_for(student_id: str, item: ob.Item) -> Any:
    b = _bursaries()
    ref = item.evidence_ref or ""
    if ref.startswith(REF_PREFIX):
        try:
            app = b.get_application(int(ref[len(REF_PREFIX):]))
        except ValueError:
            app = None
        if app is not None and app.student_id == student_id:
            return app
    chk = ob.get_checklist(item.checklist_id)
    year = chk.academic_year if chk else None
    apps = [a for a in b.list_applications(student_id=student_id)
            if not year or not a.academic_year or a.academic_year == year]
    if not apps:
        return None
    live = [a for a in apps if a.status not in ("Cancelled", "Withdrawn")]
    pool = live or apps
    return max(pool, key=lambda a: (a.status not in _NOT_APPLIED,
                                    a.application_id))


def bursary_rule(student_id: str, item: ob.Item
                 ) -> tuple[bool | None, str | None, str]:
    try:
        app = _application_for(student_id, item)
    except ImportError:
        return None, None, ""
    if app is None:
        if item.required:
            return False, None, (
                f"'{item.task_name}': no bursary application is on file for "
                f"{student_id}. Open one in Bursaries, or say where the "
                "evidence is.")
        return None, None, ""
    if app.status in _NOT_APPLIED:
        return False, None, (
            f"'{item.task_name}': bursary application #{app.application_id} "
            f"is {app.status} — the learner has not applied yet. Submit it, "
            "or say where the evidence is.")
    return True, f"{REF_PREFIX}{app.application_id}", ""


ob.register_evidence_rule(BURSARY_KEY, bursary_rule)


def link_application(checklist_id: int, application_id: int, *,
                     required: bool = True) -> ob.Item:
    """Point the checklist's bursary task at ``application_id`` (adding
    the task when missing) and make it required. The task stays open
    until the application is submitted."""
    ob._require_writer("linking onboarding tasks")
    chk = ob.get_checklist(checklist_id)
    if chk is None:
        raise ob.ValidationError(f"No checklist #{checklist_id}")
    app = _bursaries().get_application(int(application_id))
    if app is None or app.student_id != chk.student_id:
        raise ob.ValidationError(f"Bursary application #{application_id} is "
                                 f"not {chk.student_id}'s")
    item = next((i for i in ob.list_items(checklist_id=checklist_id)
                 if i.key == BURSARY_KEY), None)
    if item is None:
        item = ob.create_item({
            "checklist_id": checklist_id, "task_name": BURSARY_KEY,
            "category": "Finance", "required": required,
            "owner_role": "Finance", "source": "bursary"})
    elif required and not item.required:
        item = ob.update_item(item.item_id, {"required": True})
    ref = f"{REF_PREFIX}{app.application_id}"
    with ob._connect() as conn:
        conn.execute("UPDATE onboarding_items SET evidence_ref = ?, "
                     "updated_at = datetime('now') WHERE item_id = ? "
                     "AND status NOT IN ('Done', 'N/A')",
                     (ref, item.item_id))
        ob._log(conn, checklist_id=checklist_id, student_id=chk.student_id,
                item_id=item.item_id, action="Linked",
                detail=f"bursary application #{app.application_id} "
                       f"({app.status})")
        conn.commit()
    out = ob.get_item(item.item_id)
    assert out is not None
    return out


def sync_open_items(academic_year: str | None = None) -> list[str]:
    """Tick every open bursary task whose application has been submitted
    (through ``set_item_status``, so the rule applies). Returns lines."""
    ob._require_writer("changing onboarding tasks")
    lines: list[str] = []
    for chk in ob.list_checklists(open_only=True, academic_year=academic_year):
        for item in ob.list_items(checklist_id=chk.checklist_id):
            if item.key != BURSARY_KEY or item.is_done:
                continue
            ok, ref, _msg = bursary_rule(chk.student_id, item)
            if ok:
                ob.set_item_status(item.item_id, "Done")
                lines.append(f"{chk.student_id}: bursary task ticked ({ref})")
    return lines
