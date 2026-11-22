"""Adding a learner from the Add Student form, with their needs and login.

The other systems' add-learner forms ask about needs and medical
information; the sixth form already keeps both in their own registers, so
this sends what the form collects there instead of adding a second copy
on the student record:

* LLDD / EHC Plan / SEND details open an entry on the SEND register for
  the SENCO to review. The census and ILR read LLDD and EHCP from that
  register, so it is the one place they belong. Admissions conversion
  does the same for an applicant's declared needs.
* Medical notes are added to the learner's medical profile notes for the
  medical team.

The login gets a random temporary password, shown to the member of staff
once (:attr:`AddedLearner.password`) and in the welcome e-mail.
"""

from __future__ import annotations

import datetime as _dt
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.learners.students import students as _s
from education_system.systems.sixth_form.domain.learners.students.student_profile import (
    NOTES_MAX_LENGTH,
    ValidationError,
)

logger = logging.getLogger(__name__)

#: Form keys that are routed to the registers, not stored on the record.
NEEDS_KEYS = ("has_lldd", "has_ehcp", "send_details", "medical_notes")

# No 0/O, 1/l/I: the password gets read out and typed in by hand.
_PASSWORD_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def temporary_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(12))


@dataclass
class AddedLearner:
    student: Any
    #: The login's temporary password. Show it once; it is not kept.
    password: str
    #: One line per register the needs went to (or why they didn't).
    needs: list[str] = field(default_factory=list)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(value)


def validate_needs(data: dict[str, Any]) -> dict[str, Any]:
    """The needs part of the form, checked before anything is written."""
    out = {
        "has_lldd": _truthy(data.get("has_lldd")),
        "has_ehcp": _truthy(data.get("has_ehcp")),
        "send_details": str(data.get("send_details") or "").strip(),
        "medical_notes": str(data.get("medical_notes") or "").strip(),
    }
    for key, label in (("send_details", "SEND details"),
                       ("medical_notes", "Medical notes")):
        if len(out[key]) > NOTES_MAX_LENGTH:
            raise ValidationError(f"{label} must be {NOTES_MAX_LENGTH} characters or fewer")
    return out


def add_learner(data: dict[str, Any], *, allow_duplicate: bool = False) -> AddedLearner:
    """Create the record and login, then send needs to their registers.

    Raises what :func:`students.create_student` raises (``PossibleDuplicate``
    included) before anything is written. A register that refuses the
    needs does not undo the learner; the reason is in ``needs`` and the
    record history.
    """
    record = {k: v for k, v in data.items() if k not in NEEDS_KEYS}
    needs = validate_needs(data)
    password = temporary_password()
    student = _s.create_student(record, allow_duplicate=allow_duplicate,
                                password=password)
    added = AddedLearner(student=student, password=password)
    sid = student.student_id
    if needs["has_lldd"] or needs["has_ehcp"] or needs["send_details"]:
        added.needs.append(_to_send_register(sid, needs))
    if needs["medical_notes"]:
        added.needs.append(_to_medical_profile(sid, needs["medical_notes"]))
    return added


def _log_sensitive(area: str, action: str, sid: str) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import access

    try:
        access.log_sensitive_access(access.current(), area, action, student_id=sid)
    except Exception:  # noqa: BLE001 - logging must not block the work
        logger.warning("Could not log %s access for %s", area, sid, exc_info=True)


def _to_send_register(sid: str, needs: dict[str, Any]) -> str:
    try:
        from education_system.systems.sixth_form.domain.pastoral.send import send as _send

        declared = [label for key, label in (("has_lldd", "LLDD"), ("has_ehcp", "EHC Plan"))
                    if needs[key]]
        notes = ("Entered on the Add Student form"
                 + (f" ({', '.join(declared)} declared)" if declared else "")
                 + ". Primary need to be confirmed by the SENCO."
                 + (f"\n\nSEND details:\n{needs['send_details']}"
                    if needs["send_details"] else ""))
        entry = _send.create_entry({
            "student_id": sid,
            "register_status": "EHCP" if needs["has_ehcp"] else "Awaiting Assessment",
            "primary_need": "Other",
            "date_added": _dt.date.today().isoformat(),
            "cycle_stage": "Assess", "status": "Active", "notes": notes,
        })
    except Exception as exc:  # noqa: BLE001 - the learner is already saved
        logger.exception("SEND register entry for new student %s failed", sid)
        _s.record_history(sid, "record", note=f"SEND needs not added to the register: {exc}")
        return f"SEND register: not added ({exc}). Add them under SEND."
    _log_sensitive("send", "add student: open SEND register entry", sid)
    _s.record_history(sid, "record",
                      note=f"SEND register entry #{entry.entry_id} opened from the add form")
    return (f"SEND register: entry #{entry.entry_id} ({entry.register_status}) "
            "for the SENCO to review.")


def _to_medical_profile(sid: str, text: str) -> str:
    try:
        from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
            medical_records as _med,
        )

        today = _dt.date.today().isoformat()
        block = f"Entered on the Add Student form ({today}):\n{text}"
        old = _med.get_profile(sid)
        profile: dict[str, Any] = {k: getattr(old, k) for k in (
            "nhs_number", "blood_group", "gp_name", "gp_practice", "gp_phone",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_rel", "last_reviewed", "notes")} if old else {}
        profile["student_id"] = sid
        profile["notes"] = f"{profile['notes']}\n\n{block}" if profile.get("notes") else block
        _med.save_profile(profile)
    except Exception as exc:  # noqa: BLE001 - the learner is already saved
        logger.exception("Medical profile notes for new student %s failed", sid)
        _s.record_history(sid, "record", note=f"Medical notes not saved: {exc}")
        return f"Medical profile: not saved ({exc}). Add them under Medical Records."
    _log_sensitive("medical", "add student: medical profile notes", sid)
    _s.record_history(sid, "record", note="Medical notes added to the medical profile")
    return "Medical profile: notes added for the medical team."
