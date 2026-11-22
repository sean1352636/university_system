"""Onboarding in the student and parent portals.

The learner (student portal) and a linked parent (parent portal) can see
the learner's current onboarding checklist and complete the tasks owned
by them (``owner_role`` ``learner`` / ``parent``). Same rule as
:mod:`parent_portal.learner_view`: the caller passes only the signed-in
learner's own ``student_id`` (or the parent's ``account_id``, whose link
to the learner is checked); no id is taken from the screen.

What they see: task name, category, required, status, due date and
whether they may complete it. Never staff notes, evidence, N/A / blocked
reasons or who did what, and never sensitive tasks (care, young carer,
free meals, DSL) — those are left out entirely.

Completing a task goes through :func:`onboarding.set_item_status` with
the portal user bound as the actor (``learner:<id>`` /
``parent:<username>``), so the evidence rules and history apply: a task
that needs a record staff hold (an ID card, a tutor group) cannot be
ticked from the portal until the record exists. A parent-owned consent
task is answered through :func:`onboarding.record_consent`, then
:func:`consent_followups.after_consent`.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

LEARNER, PARENT = "learner", "parent"
ValidationError = ob.ValidationError


def _sid(student_id: str) -> str:
    sid = (student_id or "").strip() if isinstance(student_id, str) else ""
    if not sid:
        raise ValidationError("A signed-in learner's student id is required")
    return sid


@contextlib.contextmanager
def _as_portal_user(username: str) -> Iterator[None]:
    """Bind the portal user for one onboarding write, with only the
    onboarding write capability (checks on what they may do are made
    before this)."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.Principal(username=username, user_id=None, role="portal",
                         capabilities=frozenset({access.ADMISSIONS}))
    token = access.bind_request(p)
    try:
        yield
    finally:
        access.unbind_request(token)


def _current_checklist(sid: str) -> ob.Checklist | None:
    lists = ob.list_checklists(student_id=sid, open_only=True)
    if not lists:
        lists = [c for c in ob.list_checklists(student_id=sid)
                 if c.status == "Completed"]
    return lists[0] if lists else None


def _raw_items(checklist_id: int) -> list[ob.Item]:
    # Read the rows directly: sensitive tasks are dropped below, so the
    # staff-side masking (and its access log) is not needed here.
    with ob._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM onboarding_items WHERE checklist_id = ? "
            "ORDER BY sort_order, item_id", (checklist_id,)).fetchall()
    return [ob._row_item(r) for r in rows]


def _can_complete(item: ob.Item, role: str) -> bool:
    if item.is_done or item.sensitive or item.key in ob.ID_ITEMS:
        return False
    if (item.owner_role or "").lower() != role:
        return False
    return not ob.is_consent_item(item) or role == PARENT


def _task_view(item: ob.Item, role: str) -> dict[str, Any]:
    return {"item_id": item.item_id, "task": item.task_name,
            "category": item.category, "required": item.required,
            "status": item.status, "due_date": item.due_date,
            "completed_on": item.completed_on,
            "yours": (item.owner_role or "").lower() == role,
            "can_complete": _can_complete(item, role),
            "is_consent": ob.is_consent_item(item)}


def _view(sid: str, role: str) -> dict[str, Any] | None:
    ob.init_db()
    c = _current_checklist(sid)
    if c is None:
        return None
    tasks = [_task_view(i, role) for i in _raw_items(c.checklist_id)
             if not i.sensitive]
    return {"checklist_id": c.checklist_id, "name": c.name,
            "status": c.status, "academic_year": c.academic_year,
            "due_date": c.due_date,
            "done": sum(1 for t in tasks if t["status"] in
                        ob.DONE_ITEM_STATUSES),
            "total": len(tasks),
            "to_do": [t for t in tasks if t["can_complete"]],
            "tasks": tasks}


def _require_task(sid: str, item_id: int, role: str) -> ob.Item:
    c = _current_checklist(sid)
    item = ob._get_item_raw(int(item_id))
    if c is None or item is None or item.checklist_id != c.checklist_id \
            or item.sensitive:
        raise ValidationError("That task is not on your onboarding checklist")
    if not _can_complete(item, role):
        raise ValidationError(f"'{item.task_name}' is completed by college "
                              "staff, or is already done")
    return item


def _complete(sid: str, item: ob.Item, actor: str,
              note: str | None) -> dict[str, Any]:
    problem = ob.evidence_problem(item)
    if problem is not None:
        raise ValidationError(f"'{item.task_name}' can't be completed here "
                              "yet — the college has to record it first.")
    with _as_portal_user(actor):
        if note and note.strip():
            stamp = f"{actor} (portal): {note.strip()[:500]}"
            ob.update_item(item.item_id, {"notes": (
                f"{item.notes}\n{stamp}" if item.notes else stamp)})
        out = ob.set_item_status(item.item_id, "Done", completed_by=actor)
    return {"item_id": out.item_id, "status": out.status}


# ── Student portal ─────────────────────────────────────────────────

def learner_checklist(student_id: str) -> dict[str, Any] | None:
    """The learner's current checklist (None when there is none)."""
    return _view(_sid(student_id), LEARNER)


def learner_complete(student_id: str, item_id: int, *,
                     note: str | None = None) -> dict[str, Any]:
    """The learner marks one of their own tasks done."""
    sid = _sid(student_id)
    item = _require_task(sid, item_id, LEARNER)
    return _complete(sid, item, f"learner:{sid}", note)


# ── Parent portal ──────────────────────────────────────────────────

def _parent(account_id: int, student_id: str) -> tuple[Any, str]:
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
        parent_portal as _pp,
    )
    try:
        account = _pp._require_account(int(account_id))
        sid = _pp._require_link(int(account_id), student_id)
    except _pp.ValidationError as e:
        raise ValidationError(str(e)) from None
    return account, sid


def parent_checklist(account_id: int, student_id: str
                     ) -> dict[str, Any] | None:
    """A linked child's current checklist, for their parent."""
    _account, sid = _parent(account_id, student_id)
    return _view(sid, PARENT)


def parent_complete(account_id: int, student_id: str, item_id: int, *,
                    note: str | None = None) -> dict[str, Any]:
    """The parent marks one of their (non-consent) tasks done."""
    account, sid = _parent(account_id, student_id)
    item = _require_task(sid, item_id, PARENT)
    if ob.is_consent_item(item):
        raise ValidationError("Answer a consent task with yes or no")
    return _complete(sid, item, f"parent:{account.username}", note)


def parent_consent(account_id: int, student_id: str, item_id: int, *,
                   granted: bool) -> dict[str, Any]:
    """The parent answers a consent task they own: the decision is
    recorded in the GDPR consent register (given by the parent) and a
    refusal opens a follow-up task for staff."""
    account, sid = _parent(account_id, student_id)
    item = _require_task(sid, item_id, PARENT)
    if not ob.is_consent_item(item):
        raise ValidationError(f"'{item.task_name}' is not a consent task")
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        consent_followups as _cf,
    )
    actor = f"parent:{account.username}"
    with _as_portal_user(actor):
        link = ob.record_consent(
            item.item_id, granted=bool(granted),
            given_by=f"{account.full_name} (parent portal)",
            recorded_by=actor)
        try:
            _cf.after_consent(link)
        except Exception:  # noqa: BLE001 — the consent itself is recorded
            logger.exception("Consent follow-up for item #%s", item.item_id)
    return {"item_id": item.item_id, "state": link.state,
            "consent_id": link.consent_id}
