"""Record changes made from Advanced Search results.

Search screens change records only through the student domain's own
functions (``set_status``/``withdraw_student``/``update_student``), so a
status change from a result list has the same side effects, history and
checks as one made in the Student Directory. Every function here needs
``students.manage`` on the signed-in account.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._db import clear_cache
from .models import ValidationError

#: Fields the duplicate-link fills on the kept record when it is empty.
MERGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name", "First name"), ("middle_name", "Middle"),
    ("last_name", "Last name"), ("preferred_name", "Preferred name"),
    ("date_of_birth", "Date of birth"), ("gender", "Gender"),
    ("phone", "Phone"), ("personal_email", "Personal email"),
    ("address", "Address"), ("postcode", "Postcode"),
    ("previous_school", "Previous school"), ("nationality", "Nationality"),
    ("first_language", "First language"), ("uln", "ULN"), ("uci", "UCI"),
    ("emergency_contact_name", "Emerg. name"),
    ("emergency_contact_phone", "Emerg. phone"),
    ("emergency_contact_relation", "Emerg. rel"),
)

#: Fields the inline editor may change.
INLINE_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name", "First name"), ("middle_name", "Middle"),
    ("last_name", "Last name"), ("preferred_name", "Preferred name"),
    ("phone", "Phone"),
)


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


def _require_manage(action: str) -> Any:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    p.require(access.STUDENTS_MANAGE, action)
    return p


def statuses() -> tuple[str, ...]:
    return _students().STATUSES


@dataclass
class BulkStatusResult:
    status: str
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def bulk_set_status(student_ids: list[str], status: str, *,
                    reason: str | None = None,
                    leaving_date: str | None = None) -> BulkStatusResult:
    """Change many students' status through ``set_status``. ``Left`` needs
    a reason (it withdraws the learner: enrolments, tutor group, login),
    and a Left learner moved back on roll is reinstated."""
    p = _require_manage("bulk status changes")
    st = _students()
    status = (status or "").strip()
    if status not in st.STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(st.STATUSES)}")
    if status == "Left" and not (reason or "").strip():
        raise ValidationError("A reason is needed to mark students as Left.")
    out = BulkStatusResult(status=status)
    for sid in dict.fromkeys(s for s in student_ids if s):
        try:
            before = st.get_student(sid)
            if before is None:
                out.failed[sid] = "no such student"
                continue
            if before.status == status:
                out.unchanged.append(sid)
                continue
            if status == "Left":
                st.withdraw_student(sid, reason=reason.strip(),
                                    leaving_date=leaving_date or None,
                                    by=p.username or None)
            else:
                st.set_status(sid, status, reason=reason or None,
                              by=p.username or None)
            out.changed.append(sid)
        except Exception as exc:  # noqa: BLE001 — reported per student
            out.failed[sid] = str(exc)
    from .annotations import log_action
    log_action("bulk status", f"→ {status}: {reason or ''}".strip(),
               len(out.changed))
    clear_cache()
    return out


@dataclass
class DuplicateLink:
    kept: str
    duplicate: str
    filled: list[str]
    linked_records: dict[str, int]


def link_duplicate(keep_id: str, duplicate_id: str) -> DuplicateLink:
    """Record that *duplicate_id* is the same learner as *keep_id*.

    Empty fields on the kept record are filled from the duplicate through
    ``update_student``, both records' history says which is which, and the
    duplicate is tagged ``merged-duplicate`` in the search annotations.
    The duplicate's own records (attendance, marks…) are not moved; the
    counts are returned so the screen can say what is still on it, and the
    duplicate stays on roll until someone withdraws it in the directory.
    """
    p = _require_manage("linking duplicate students")
    st = _students()
    if keep_id == duplicate_id:
        raise ValidationError("Pick two different students.")
    keep, dup = st.get_student(keep_id), st.get_student(duplicate_id)
    if keep is None or dup is None:
        raise ValidationError("Could not load both student records.")
    payload: dict[str, Any] = {}
    filled: list[str] = []
    for attr, label in MERGE_FIELDS:
        mine, theirs = getattr(keep, attr, None), getattr(dup, attr, None)
        if not (mine or "") and (theirs or ""):
            payload[attr] = theirs
            filled.append(label)
    if payload:
        st.update_student(keep_id, payload)
    who = p.username or None
    st.record_history(keep_id, "Duplicate", None, duplicate_id, changed_by=who,
                      note=f"{duplicate_id} is a duplicate of this record")
    st.record_history(duplicate_id, "Duplicate", None, keep_id, changed_by=who,
                      note=f"Duplicate of {keep_id}")
    from . import annotations as ann
    store = ann.load_all()
    entry = store.setdefault(ann.key("students", duplicate_id), {})
    entry["merged_into"] = ann.key("students", keep_id)
    tags = entry.setdefault("tags", [])
    if "merged-duplicate" not in tags:
        tags.append("merged-duplicate")
    ann.save_all(store)
    ann.log_action("link duplicate", f"{duplicate_id} → {keep_id}", 1)
    clear_cache()
    return DuplicateLink(kept=keep_id, duplicate=duplicate_id, filled=filled,
                         linked_records=st.linked_record_counts(duplicate_id))


def inline_update(student_id: str, changes: dict[str, Any], *,
                  status: str | None = None,
                  reason: str | None = None) -> Any:
    """Save the inline editor: name/phone via ``update_student`` (which
    keeps every field not passed), status via ``set_status``."""
    p = _require_manage("editing students")
    st = _students()
    allowed = {a for a, _ in INLINE_FIELDS}
    data = {k: v for k, v in changes.items() if k in allowed}
    if data:
        st.update_student(student_id, data)
    if status:
        current = st.get_student(student_id)
        if current is not None and current.status != status:
            if status == "Left" and not (reason or "").strip():
                raise ValidationError(
                    "A reason is needed to mark a student as Left.")
            st.set_status(student_id, status, reason=reason or None,
                          by=p.username or None)
    clear_cache()
    return st.get_student(student_id)
