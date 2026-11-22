"""Photo and identity-document check at enrolment.

One row per student in ``enrolment_identity_checks``:

* **photo** — the file is copied into the sixth-form data directory
  (``<SIXTH_FORM_DATA_DIR>/student_photos/<student_id>/``) and only its
  path is stored, with who added it and when;
* **ID document** — the type seen (passport, driving licence …), the
  last four characters of its number only (the full number is never
  stored), who checked it and on what date, plus the right-to-study
  outcome and any visa type / expiry.

Every ID check is also appended to ``enrolment_identity_check_history``,
so re-recording a check never loses the earlier one. Conversion copies
the applicant's admissions identity check across with
:func:`record_from_admissions` (``source`` names the applicant).

Recording the ID check ticks every onboarding ID task on the student's
open checklist whose rule now passes (right to study needs a "Yes"
outcome); correcting the check so it no longer supports a task, or
revoking it (:func:`revoke_id_check`), re-opens the tasks ticked from it.

Reads of the photo and ID-document fields are open (the onboarding and
student screens use them). **Right to study and visa** details are
immigration data: only ``admissions``, ``students.manage`` or
``safeguarding`` see them, and every such read is written to the sixth
form sensitive-access log; anyone else gets :data:`RESTRICTED` in those
fields. :func:`id_history` and :func:`visa_expiring` need the capability.
Writes need ``admissions`` or ``students.manage``.

:func:`outstanding` (the "still to do" list) covers the live enrolments of
one academic year — the current one by default — and flags a missing
photo, a missing ID check, an unconfirmed right to study and a visa that
has expired or expires within :data:`VISA_WARNING_DAYS`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import secrets
import shutil
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ENROLMENTS_DB

ID_DOCUMENT_TYPES: tuple[str, ...] = (
    "Passport", "Driving licence", "Birth certificate",
    "National identity card", "Biometric residence permit / eVisa",
    "Other",
)
PHOTO_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".gif",
                                     ".bmp", ".webp")
MAX_PHOTO_BYTES: int = 5 * 1024 * 1024
#: The onboarding item ticked by an ID check.
ID_ONBOARDING_TASK: str = "Photocopy of ID / passport"
#: Shown in the right-to-study / visa fields to staff who may not see them.
RESTRICTED: str = "(restricted)"
#: A visa expiring within this many days is flagged.
VISA_WARNING_DAYS: int = 60
#: Sensitive-access log area for right-to-study / visa reads.
SENSITIVE_AREA: str = "right to study"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_identity_checks (
    student_id        TEXT PRIMARY KEY,
    photo_path        TEXT,
    photo_added_at    TEXT,
    photo_added_by    TEXT,
    id_document_type  TEXT,
    id_number_last4   TEXT,
    id_checked_by     TEXT,
    id_checked_on     TEXT,
    notes             TEXT,
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrolment_identity_check_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    at                TEXT NOT NULL DEFAULT (datetime('now')),
    id_document_type  TEXT,
    id_number_last4   TEXT,
    right_to_study    TEXT,
    visa_type         TEXT,
    visa_expiry       TEXT,
    id_checked_by     TEXT,
    id_checked_on     TEXT,
    notes             TEXT,
    source            TEXT,
    recorded_by       TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_eich_student
    ON enrolment_identity_check_history(student_id);
"""

#: Columns added to ``enrolment_identity_checks`` after the first schema.
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("right_to_study", "TEXT"),
    ("visa_type", "TEXT"),
    ("visa_expiry", "TEXT"),
    ("source", "TEXT"),
)


class ValidationError(ValueError):
    """Raised for invalid photo / ID input."""


@dataclass
class IdentityCheck:
    student_id: str
    photo_path: str | None
    photo_added_at: str | None
    photo_added_by: str | None
    id_document_type: str | None
    id_number_last4: str | None
    id_checked_by: str | None
    id_checked_on: str | None
    notes: str | None
    updated_at: str | None
    right_to_study: str | None = None
    visa_type: str | None = None
    visa_expiry: str | None = None
    source: str | None = None

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_path) and Path(self.photo_path).is_file()

    @property
    def id_checked(self) -> bool:
        return bool(self.id_document_type and self.id_checked_on)


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        have = {r["name"] for r in conn.execute(
            "PRAGMA table_info(enrolment_identity_checks)").fetchall()}
        for name, ddl in _ADDED_COLUMNS:
            if name not in have:
                conn.execute(f"ALTER TABLE enrolment_identity_checks "
                             f"ADD COLUMN {name} {ddl}")
        conn.commit()
    _DB_READY = True


def photos_dir() -> Path:
    d = paths.SIXTH_FORM_DATA_DIR / "student_photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _row(r: db.Row) -> IdentityCheck:
    return IdentityCheck(**{k: r[k] for k in r.keys()})


def _require_writer(action: str) -> None:
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    _guard.require_any((access.ADMISSIONS, access.STUDENTS_MANAGE), action)


def _username() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def _require_student(student_id: str) -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    sid = (student_id or "").strip()
    if not sid or _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid or '(blank)'}")
    return sid


def _ensure_row(conn: db.Connection, student_id: str) -> None:
    conn.execute("INSERT OR IGNORE INTO enrolment_identity_checks "
                 "(student_id) VALUES (?)", (student_id,))


# ── Who may see immigration data ───────────────────────────────────

_IMMIGRATION_FIELDS: tuple[str, ...] = ("right_to_study", "visa_type",
                                        "visa_expiry")


def can_see_immigration() -> bool:
    """Whether the signed-in user may see right to study and visa
    details (``admissions``, ``students.manage`` or ``safeguarding``)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return any(_guard.can(c) for c in (access.ADMISSIONS,
                                       access.STUDENTS_MANAGE,
                                       access.SAFEGUARDING))


def _require_immigration(action: str) -> None:
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    _guard.require_any((access.ADMISSIONS, access.STUDENTS_MANAGE,
                        access.SAFEGUARDING), action)


def _log_read(action: str, student_id: str | None = None) -> None:
    """One sensitive-access row (never raises)."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        access.log_sensitive_access(access.current(), SENSITIVE_AREA, action,
                                    student_id=student_id,
                                    record_ref=(f"student:{student_id}"
                                                if student_id else None))
    except Exception:  # noqa: BLE001 — logging must not block the work
        logger.warning("Could not log right-to-study read", exc_info=True)


def _has_immigration(c: IdentityCheck) -> bool:
    return any(getattr(c, f) for f in _IMMIGRATION_FIELDS)


def _redact(c: IdentityCheck) -> IdentityCheck:
    for f in _IMMIGRATION_FIELDS:
        if getattr(c, f):
            setattr(c, f, RESTRICTED)
    return c


# ── Reads ──────────────────────────────────────────────────────────

def _raw_check(student_id: str) -> IdentityCheck | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM enrolment_identity_checks "
                         "WHERE student_id = ?", (student_id,)).fetchone()
    return _row(r) if r else None


def _raw_checks() -> list[IdentityCheck]:
    init_db()
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM enrolment_identity_checks ORDER BY student_id")]


def get_check(student_id: str) -> IdentityCheck | None:
    """The student's check. Right to study / visa come back as
    :data:`RESTRICTED` unless the reader may see them (then the read is
    logged)."""
    c = _raw_check(student_id)
    if c is None or not _has_immigration(c):
        return c
    if can_see_immigration():
        _log_read("view", student_id)
        return c
    return _redact(c)


def list_checks() -> list[IdentityCheck]:
    """Every check (immigration fields as in :func:`get_check`; one log
    row for the list)."""
    rows = _raw_checks()
    if not any(_has_immigration(c) for c in rows):
        return rows
    if can_see_immigration():
        _log_read("list")
        return rows
    return [_redact(c) for c in rows]


def visa_state(c: IdentityCheck | None, *, within_days: int = VISA_WARNING_DAYS,
               today: str | None = None) -> str | None:
    """'expired', 'expiring' or None for an (unredacted) check."""
    if c is None or not c.visa_expiry or c.visa_expiry == RESTRICTED:
        return None
    now = _dt.date.fromisoformat(today) if today else _dt.date.today()
    try:
        expiry = _dt.date.fromisoformat(c.visa_expiry)
    except ValueError:
        return None
    if expiry < now:
        return "expired"
    if expiry <= now + _dt.timedelta(days=within_days):
        return "expiring"
    return None


def right_to_study_confirmed(c: IdentityCheck | None) -> bool:
    return bool(c and (c.right_to_study or "").startswith("Yes"))


@dataclass
class OutstandingCheck:
    """What is still to do for one learner. ``visa_expiry`` is None for
    readers who may not see immigration data (``visa`` still says that
    something needs attention)."""
    student_id: str
    has_photo: bool
    id_checked: bool
    right_to_study: str        # 'confirmed' | 'unknown' | 'no' | 'restricted'
    visa: str | None           # 'expired' | 'expiring' | None
    visa_expiry: str | None = None

    @property
    def problems(self) -> list[str]:
        out = []
        if not self.has_photo:
            out.append("no photo")
        if not self.id_checked:
            out.append("no ID check")
        if self.right_to_study == "unknown":
            out.append("right to study not confirmed")
        elif self.right_to_study == "no":
            out.append("no right to study recorded")
        elif self.right_to_study == "restricted":
            out.append("right to study needs checking")
        if self.visa:
            out.append(f"visa {self.visa}"
                       + (f" ({self.visa_expiry})" if self.visa_expiry
                          else ""))
        return out

    @property
    def is_complete(self) -> bool:
        return not self.problems


def _status_for(sid: str, c: IdentityCheck | None, see: bool,
                within_days: int) -> OutstandingCheck:
    rts = "unknown"
    if right_to_study_confirmed(c):
        rts = "confirmed"
    elif c is not None and c.right_to_study == "No":
        rts = "no"
    visa = visa_state(c, within_days=within_days)
    if not see and rts in ("no",):
        rts = "restricted"
    return OutstandingCheck(
        student_id=sid, has_photo=bool(c and c.has_photo),
        id_checked=bool(c and c.id_checked), right_to_study=rts, visa=visa,
        visa_expiry=(c.visa_expiry if see and visa and c else None))


def _live_student_ids(academic_year: str | None) -> list[str]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    year = academic_year or _enrolments.current_academic_year()
    return sorted({e.student_id for e in _enrolments.list_enrolments(
        academic_year=year) if e.is_live})


def check_status(student_id: str, *, within_days: int = VISA_WARNING_DAYS
                 ) -> OutstandingCheck:
    """The :class:`OutstandingCheck` for one learner (logged when the
    reader sees immigration data)."""
    see = can_see_immigration()
    c = _raw_check(student_id)
    if see and c is not None and _has_immigration(c):
        _log_read("status", student_id)
    return _status_for(student_id, c, see, within_days)


def outstanding_detail(academic_year: str | None = None, *,
                       within_days: int = VISA_WARNING_DAYS
                       ) -> list[OutstandingCheck]:
    """Learners with a live enrolment in the year (default: the current
    one) who still have something to do."""
    see = can_see_immigration()
    checks = {c.student_id: c for c in _raw_checks()}
    out = [_status_for(sid, checks.get(sid), see, within_days)
           for sid in _live_student_ids(academic_year)]
    out = [o for o in out if not o.is_complete]
    if see and any(o.visa or o.right_to_study == "no" for o in out):
        _log_read("outstanding list")
    return out


def outstanding(academic_year: str | None = None) -> list[tuple[str, bool, bool]]:
    """(student_id, has_photo, id_checked) for learners with a live
    enrolment in the year (default: the current one) who are missing a
    photo or ID check, have no confirmed right to study, or whose visa has
    expired / expires soon. :func:`outstanding_detail` says which."""
    return [(o.student_id, o.has_photo, o.id_checked)
            for o in outstanding_detail(academic_year)]


@dataclass
class VisaRow:
    student_id: str
    visa_type: str | None
    visa_expiry: str
    days_left: int             # negative once expired

    @property
    def expired(self) -> bool:
        return self.days_left < 0


def visa_expiring(within_days: int = VISA_WARNING_DAYS, *,
                  today: str | None = None) -> list[VisaRow]:
    """Learners with a live enrolment (any year) whose visa has expired
    or expires within *within_days*, soonest first. Needs ``admissions``,
    ``students.manage`` or ``safeguarding``; the read is logged."""
    _require_immigration("visa expiry dates")
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    live = {e.student_id for e in _enrolments.list_enrolments() if e.is_live}
    now = _dt.date.fromisoformat(today) if today else _dt.date.today()
    out = []
    for c in _raw_checks():
        if c.student_id not in live:
            continue
        if visa_state(c, within_days=within_days, today=now.isoformat()):
            expiry = _dt.date.fromisoformat(c.visa_expiry or "")
            out.append(VisaRow(c.student_id, c.visa_type, expiry.isoformat(),
                               (expiry - now).days))
    _log_read(f"visa expiry list ({len(out)})")
    return sorted(out, key=lambda r: r.visa_expiry)


# ── Photo ──────────────────────────────────────────────────────────

def set_photo(student_id: str, source_path: str, *,
              by: str | None = None) -> IdentityCheck:
    """Copy a photo into the managed folder and record it."""
    init_db()
    _require_writer("recording student photos")
    sid = _require_student(student_id)
    src = Path(source_path)
    if not src.is_file():
        raise ValidationError(f"File not found: {source_path}")
    if src.suffix.lower() not in PHOTO_EXTENSIONS:
        raise ValidationError("Photo must be an image file ("
                              + ", ".join(PHOTO_EXTENSIONS) + ")")
    if src.stat().st_size > MAX_PHOTO_BYTES:
        raise ValidationError("Photo is larger than 5 MB")
    dest_dir = photos_dir() / sid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{secrets.token_hex(4)}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    old = _raw_check(sid)
    with _connect() as conn:
        _ensure_row(conn, sid)
        conn.execute(
            "UPDATE enrolment_identity_checks SET photo_path = ?, "
            "photo_added_at = datetime('now'), photo_added_by = ?, "
            "updated_at = datetime('now') WHERE student_id = ?",
            (str(dest), by or _username(), sid))
        conn.commit()
    # Keep only the current photo file for this student.
    if old and old.photo_path and old.photo_path != str(dest):
        try:
            p = Path(old.photo_path)
            if p.is_file() and photos_dir() in p.parents:
                p.unlink()
        except OSError:
            logger.warning("Could not remove old photo %s", old.photo_path)
    logger.info("Photo recorded for %s", sid)
    out = get_check(sid)
    assert out is not None
    return out


def remove_photo(student_id: str) -> bool:
    _require_writer("removing student photos")
    c = _raw_check(student_id)
    if c is None or not c.photo_path:
        return False
    try:
        p = Path(c.photo_path)
        if p.is_file() and photos_dir() in p.parents:
            p.unlink()
    except OSError:
        logger.warning("Could not delete photo file %s", c.photo_path)
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolment_identity_checks SET photo_path = NULL, "
            "photo_added_at = NULL, photo_added_by = NULL, "
            "updated_at = datetime('now') WHERE student_id = ?",
            (student_id,))
        conn.commit()
    return True


# ── ID document ────────────────────────────────────────────────────

def last4(number: Any) -> str:
    """The last four letters/digits of a document number (all that is kept)."""
    s = re.sub(r"[^0-9A-Za-z]", "", str(number or "")).upper()
    if not s:
        raise ValidationError("Document number is required")
    return s[-4:]


def record_id_check(student_id: str, *, document_type: str,
                    document_number: Any, checked_by: str | None = None,
                    checked_on: str | None = None,
                    notes: str | None = None,
                    right_to_study: str | None = None,
                    visa_type: str | None = None,
                    visa_expiry: str | None = None,
                    source: str | None = None) -> IdentityCheck:
    """Record that an identity document was seen.

    Only the last four characters of ``document_number`` are stored. The
    current check is kept on the student's row and every check is
    appended to the history (:func:`id_history`). ``right_to_study`` uses
    the admissions vocabulary (``applicant_details.RIGHT_TO_STUDY``); a
    visa outcome needs ``visa_expiry``.
    """
    init_db()
    _require_writer("recording ID checks")
    sid = _require_student(student_id)
    if document_type not in ID_DOCUMENT_TYPES:
        raise ValidationError("Document type must be one of: "
                              + ", ".join(ID_DOCUMENT_TYPES))
    tail = last4(document_number)
    on = (checked_on or "").strip() or _dt.date.today().isoformat()
    try:
        on_date = _dt.date.fromisoformat(on)
    except ValueError:
        raise ValidationError("Check date must be YYYY-MM-DD") from None
    if on_date > _dt.date.today():
        raise ValidationError("Check date cannot be in the future")
    who = (checked_by or "").strip() or _username()
    if not who:
        raise ValidationError("Checked by is required")
    rts = (right_to_study or "").strip() or None
    if rts is not None:
        from education_system.systems.sixth_form.domain.admissions import (
            applicant_details as _details,
        )
        if rts not in _details.RIGHT_TO_STUDY:
            raise ValidationError("Right to study must be one of: "
                                  + ", ".join(_details.RIGHT_TO_STUDY))
    expiry = (visa_expiry or "").strip() or None
    if expiry:
        try:
            _dt.date.fromisoformat(expiry)
        except ValueError:
            raise ValidationError("Visa expiry must be YYYY-MM-DD") from None
    if rts and rts.startswith("Yes - visa") and not expiry:
        raise ValidationError("Give the visa expiry date")
    vals = (document_type, tail, rts, (visa_type or "").strip() or None,
            expiry, who, on, (notes or "").strip() or None,
            (source or "").strip() or None)
    with _connect() as conn:
        _ensure_row(conn, sid)
        conn.execute(
            "UPDATE enrolment_identity_checks SET id_document_type = ?, "
            "id_number_last4 = ?, right_to_study = ?, visa_type = ?, "
            "visa_expiry = ?, id_checked_by = ?, id_checked_on = ?, "
            "notes = ?, source = ?, updated_at = datetime('now') "
            "WHERE student_id = ?", (*vals, sid))
        conn.execute(
            "INSERT INTO enrolment_identity_check_history (student_id, "
            "id_document_type, id_number_last4, right_to_study, visa_type, "
            "visa_expiry, id_checked_by, id_checked_on, notes, source, "
            "recorded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, *vals, _username()))
        conn.commit()
    logger.info("ID check (%s) recorded for %s by %s", document_type, sid, who)
    _tick_onboarding(sid, who)
    out = get_check(sid)
    assert out is not None
    return out


def record_from_admissions(student_id: str, identity: Any,
                           applicant_id: str) -> IdentityCheck:
    """Copy an admissions identity record (``applicant_details.
    IdentityRecord``) onto the student: document type, last four, who
    checked it and when, right to study and visa."""
    if identity is None or not getattr(identity, "document_type", None):
        raise ValidationError(f"Applicant {applicant_id} has no ID check")
    return record_id_check(
        student_id, document_type=identity.document_type,
        document_number=identity.id_number_last4 or "",
        checked_by=identity.checked_by, checked_on=identity.checked_on,
        notes=identity.notes, right_to_study=identity.right_to_study,
        visa_type=identity.visa_type, visa_expiry=identity.visa_expiry,
        source=f"admissions applicant {applicant_id}")


def id_history(student_id: str) -> list[dict[str, Any]]:
    """Every ID check recorded for the student, newest first. Holds right
    to study and visa details, so it needs ``admissions``,
    ``students.manage`` or ``safeguarding`` and the read is logged."""
    _require_immigration("ID check history")
    _log_read("history", student_id)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM enrolment_identity_check_history "
            "WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
    return [dict(r) for r in rows]


def _tick_onboarding(student_id: str, who: str | None) -> None:
    """Bring the learner's open onboarding ID tasks in line with the
    current check: tick every open task whose key is an ID task
    (``onboarding.ID_ITEMS``) and whose rule now passes, and re-open the
    ones ticked from the check (evidence_ref ``idcheck``) that it no longer
    supports (e.g. right to study corrected to "No"). Never raises."""
    try:
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            onboarding as _ob,
        )
        for c in _ob.list_checklists(student_id=student_id, open_only=True):
            for item in _ob.list_items(checklist_id=c.checklist_id):
                if item.key not in _ob.ID_ITEMS:
                    continue
                try:
                    problem = _ob.evidence_problem(item)
                    if not item.is_done and not item.awaiting_second_check:
                        if problem is None:
                            _ob.tick(item.item_id, completed_by=who)
                    elif item.is_done and item.evidence_ref == ID_EVIDENCE_REF \
                            and problem is not None:
                        _reopen(_ob, item, problem)
                except Exception:
                    logger.exception("ID onboarding task #%s for %s not "
                                     "updated", item.item_id, student_id)
    except Exception:
        logger.exception("Could not update the ID onboarding tasks for %s",
                         student_id)


#: ``evidence_ref`` of an onboarding task ticked from the ID check.
ID_EVIDENCE_REF: str = "idcheck"


def _reopen(_ob, item, why: str) -> None:
    _ob.set_item_status(item.item_id, "Pending")
    note = f"Re-opened {_dt.date.today().isoformat()}: {why}"
    _ob.update_item(item.item_id, {
        "notes": f"{item.notes}\n{note}" if item.notes else note})


def reopen_onboarding(student_id: str, reason: str) -> int:
    """Re-open every done onboarding task ticked from the ID check
    (evidence_ref ``idcheck``) on the learner's open checklists, noting
    *reason*. Tasks evidenced by hand are left alone. Returns how many."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding as _ob,
    )
    n = 0
    for c in _ob.list_checklists(student_id=student_id, open_only=True):
        for item in _ob.list_items(checklist_id=c.checklist_id):
            if item.is_done and item.evidence_ref == ID_EVIDENCE_REF:
                _reopen(_ob, item, reason)
                n += 1
    return n


def revoke_id_check(student_id: str, *, reason: str) -> IdentityCheck:
    """Withdraw the current ID check (recorded in error, document found
    to be invalid …). The check fields are cleared, the history keeps the
    old check plus a "Revoked" row, and the onboarding ID tasks ticked
    from it are re-opened with the reason."""
    init_db()
    _require_writer("revoking ID checks")
    sid = _require_student(student_id)
    why = (reason or "").strip()
    if len(why.replace(" ", "")) < 5:
        raise ValidationError("Say why the ID check is revoked "
                              "(at least 5 characters)")
    c = _raw_check(sid)
    if c is None or not c.id_checked:
        raise ValidationError(f"No ID check is recorded for {sid}")
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolment_identity_checks SET id_document_type = NULL, "
            "id_number_last4 = NULL, right_to_study = NULL, visa_type = NULL, "
            "visa_expiry = NULL, id_checked_by = NULL, id_checked_on = NULL, "
            "notes = ?, source = NULL, updated_at = datetime('now') "
            "WHERE student_id = ?", (f"Revoked: {why}", sid))
        conn.execute(
            "INSERT INTO enrolment_identity_check_history (student_id, "
            "id_document_type, id_number_last4, notes, source, recorded_by) "
            "VALUES (?, ?, ?, ?, 'revoked', ?)",
            (sid, c.id_document_type, c.id_number_last4,
             f"Revoked: {why}", _username()))
        conn.commit()
    logger.info("ID check revoked for %s", sid)
    try:
        reopen_onboarding(sid, f"ID check revoked — {why}")
    except Exception:
        logger.exception("Onboarding ID tasks not re-opened for %s", sid)
    out = _raw_check(sid)
    assert out is not None
    return out
