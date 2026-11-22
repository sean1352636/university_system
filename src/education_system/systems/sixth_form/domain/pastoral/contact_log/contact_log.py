"""General contact log for the Sixth Form.

One table, ``contact_log_entries``: every phone call, e-mail, meeting,
letter or text with a learner, their parents / carers or an outside
agency — who, how, which direction, why (reason category), a summary,
the outcome, and any follow-up (owner, due date, done on).

It complements, and does not replace, the specialist records: a
safeguarding concern still goes to Safeguarding, a first-day absence
call to Attendance calling. A contact *about* safeguarding can be logged
here, but such entries — and any marked confidential — are
**restricted**: only the person who logged them and holders of the
SAFEGUARDING capability can read them.

Access
------
* Logging a contact: COMMS (every member of staff) or PASTORAL.
* Reading: your own entries always; everyone else's needs PASTORAL and
  the object-level ``can_see_student`` (a tutor sees their tutees);
  restricted entries need SAFEGUARDING as well. Every read of a
  student's log is written to the sensitive-access log.
* Editing: the person who logged it, or PASTORAL. Deleting: the person
  who logged it, or an admin.

:func:`contacts_for_student` is the entry point for the student profile.
Entries reference the student with ``ON DELETE RESTRICT``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _people, _records
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB
AREA = "contact_log"

CONTACT_WITH: tuple[str, ...] = (
    "Student", "Parent / Carer", "Social Worker", "Virtual School",
    "Personal Adviser", "Health Professional", "Police",
    "Other Agency", "Employer / Placement", "School / College",
    "University / Training Provider", "Other",
)
METHODS: tuple[str, ...] = ("Phone", "Email", "Meeting", "Video call",
                            "Letter", "Text message", "Home visit", "Other")
DIRECTIONS: tuple[str, ...] = ("Outgoing", "Incoming")
REASONS: tuple[str, ...] = (
    "Attendance", "Behaviour", "Academic progress", "Coursework / Deadlines",
    "Wellbeing", "Health / Medical", "SEND / Access arrangements",
    "Careers / Progression", "UCAS", "Finance / Bursary", "Transport",
    "Praise / Positive", "Administrative", "Safeguarding", "Other",
)
RESTRICTED_REASONS = frozenset({"Safeguarding"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact_log_entries (
    contact_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    contact_date      TEXT NOT NULL,
    contact_time      TEXT,
    contact_with      TEXT NOT NULL,
    contact_name      TEXT,
    organisation      TEXT,
    method            TEXT NOT NULL,
    direction         TEXT NOT NULL,
    reason            TEXT NOT NULL,
    summary           TEXT NOT NULL,
    outcome           TEXT,
    follow_up_required INTEGER NOT NULL DEFAULT 0,
    follow_up_owner   TEXT,
    follow_up_by      TEXT,
    follow_up_done_on TEXT,
    follow_up_notes   TEXT,
    confidential      INTEGER NOT NULL DEFAULT 0,
    recorded_by       TEXT,
    recorded_by_user  TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_contact_student ON contact_log_entries(student_id);
CREATE INDEX IF NOT EXISTS idx_contact_date    ON contact_log_entries(contact_date);
CREATE INDEX IF NOT EXISTS idx_contact_follow  ON contact_log_entries(follow_up_by)
    WHERE follow_up_required = 1 AND follow_up_done_on IS NULL;
"""


class ValidationError(ValueError):
    pass


@dataclass
class Contact:
    contact_id: int
    student_id: str
    contact_date: str
    contact_time: str | None
    contact_with: str
    contact_name: str | None
    organisation: str | None
    method: str
    direction: str
    reason: str
    summary: str
    outcome: str | None
    follow_up_required: bool
    follow_up_owner: str | None
    follow_up_by: str | None
    follow_up_done_on: str | None
    follow_up_notes: str | None
    confidential: bool
    recorded_by: str | None
    recorded_by_user: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def restricted(self) -> bool:
        return self.confidential or self.reason in RESTRICTED_REASONS

    @property
    def follow_up_open(self) -> bool:
        return self.follow_up_required and not self.follow_up_done_on

    @property
    def follow_up_overdue(self) -> bool:
        return bool(self.follow_up_open and self.follow_up_by
                    and self.follow_up_by < _records.today())


_C = _records.Col

SPEC = _records.TableSpec(
    table="contact_log_entries", id_col="contact_id", row_type=Contact,
    label="Contact", order_by="contact_date DESC, COALESCE(contact_time, '') "
                             "DESC, contact_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("contact_date", "Date", "date", required=True,
           default=_records.today),
        _C("contact_time", "Time", "time", listed=False),
        _C("contact_with", "Contact with", "choice", choices=CONTACT_WITH,
           required=True, default="Parent / Carer"),
        _C("contact_name", "Name"),
        _C("organisation", "Organisation", listed=False),
        _C("method", "Method", "choice", choices=METHODS, required=True,
           default="Phone"),
        _C("direction", "Direction", "choice", choices=DIRECTIONS,
           required=True, default="Outgoing"),
        _C("reason", "Reason", "choice", choices=REASONS, required=True),
        _C("summary", "Summary", "multiline", required=True),
        _C("outcome", "Outcome", "multiline", listed=False),
        _C("follow_up_required", "Follow-up needed", "bool"),
        _C("follow_up_owner", "Follow-up owner", listed=False),
        _C("follow_up_by", "Follow up by", "date"),
        _C("follow_up_done_on", "Followed up on", "date"),
        _C("follow_up_notes", "Follow-up notes", "multiline", listed=False),
        _C("confidential", "Confidential (restricted)", "bool",
           listed=False),
        _C("recorded_by", "Recorded by", hidden=True),
        _C("recorded_by_user", "Recorded by (login)", hidden=True),
    ))


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


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
    _DB_READY = True


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _mine(p: Any, c: Contact) -> bool:
    return bool(p.username) and c.recorded_by_user == p.username


def _can_read(p: Any, c: Contact, cache: dict[str, bool]) -> bool:
    a = _access()
    if p.is_admin or _mine(p, c):
        return True
    if not p.can(a.PASTORAL):
        return False
    if c.restricted and not p.can(a.SAFEGUARDING):
        return False
    if c.student_id not in cache:
        cache[c.student_id] = a.can_see_student(p, c.student_id,
                                                capability=a.PASTORAL)
    return cache[c.student_id]


def _log(p: Any, action: str, student_id: str | None = None,
         ref: str | None = None, allowed: bool = True) -> None:
    _access().log_sensitive_access(p, AREA, action, student_id=student_id,
                                   record_ref=ref, allowed=allowed)


def _rules(p: dict[str, Any]) -> None:
    if p["contact_date"] > _records.today():
        raise ValidationError("Contact date cannot be in the future")
    if p["follow_up_required"]:
        if p["follow_up_by"] and p["follow_up_by"] < p["contact_date"]:
            raise ValidationError(
                "Follow up by cannot be before the contact date")
    else:
        p["follow_up_owner"] = None
        p["follow_up_by"] = None
        p["follow_up_done_on"] = None
    if p["follow_up_done_on"] and p["follow_up_done_on"] < p["contact_date"]:
        raise ValidationError(
            "Followed up on cannot be before the contact date")


def _fetch(contact_id: int) -> Contact | None:
    with _connect() as conn:
        return _records.fetch(conn, SPEC, int(contact_id))


# ── CRUD ────────────────────────────────────────────────────────────

def log_contact(data: dict[str, Any]) -> Contact:
    init_db()
    a = _access()
    p_ = a.current()
    if not (p_.can(a.COMMS) or p_.can(a.PASTORAL)):
        p_.require(a.COMMS, "log contacts")
    v = _records.validate(SPEC, data, error=ValidationError,
                          student_exists=_people.student_exists)
    _rules(v)
    v["recorded_by"] = p_.staff_name or p_.username or None
    v["recorded_by_user"] = p_.username or None
    with _connect() as conn:
        new_id = _records.insert(conn, SPEC, v)
    _log(p_, "log contact", v["student_id"], f"contact:{new_id}")
    logger.info("Contact #%d logged for %s (%s, %s)", new_id,
                v["student_id"], v["method"], v["reason"])
    return _fetch(new_id)


def get_contact(contact_id: int) -> Contact | None:
    init_db()
    c = _fetch(contact_id)
    if c is None:
        return None
    p = _access().current()
    ok = _can_read(p, c, {})
    _log(p, "view contact", c.student_id, f"contact:{contact_id}", ok)
    if not ok:
        raise _access().AccessDenied(
            f"{p.username or 'This account'} may not read contact "
            f"#{contact_id}.")
    return c


def update_contact(contact_id: int, data: dict[str, Any]) -> Contact:
    init_db()
    existing = _fetch(contact_id)
    if existing is None:
        raise ValidationError(f"No contact #{contact_id}")
    a = _access()
    p = a.current()
    if not (_mine(p, existing) or p.is_admin or (
            p.can(a.PASTORAL) and _can_read(p, existing, {}))):
        _log(p, "update contact", existing.student_id,
             f"contact:{contact_id}", False)
        raise a.AccessDenied("Only the person who logged a contact, or "
                             "the pastoral team, can change it.")
    v = _records.validate(SPEC, data, error=ValidationError,
                          existing=existing)
    _rules(v)
    with _connect() as conn:
        _records.update(conn, SPEC, contact_id, v)
    _log(p, "update contact", existing.student_id, f"contact:{contact_id}")
    return _fetch(contact_id)


def complete_follow_up(contact_id: int, *, on: str | None = None,
                       notes: str | None = None) -> Contact:
    c = get_contact(contact_id)
    if c is None:
        raise ValidationError(f"No contact #{contact_id}")
    if not c.follow_up_required:
        raise ValidationError("This contact has no follow-up")
    payload: dict[str, Any] = {"follow_up_done_on": on or _records.today()}
    if notes and notes.strip():
        payload["follow_up_notes"] = notes
    return update_contact(contact_id, payload)


def delete_contact(contact_id: int) -> bool:
    init_db()
    existing = _fetch(contact_id)
    if existing is None:
        return False
    a = _access()
    p = a.current()
    if not (_mine(p, existing) or p.is_admin):
        _log(p, "delete contact", existing.student_id,
             f"contact:{contact_id}", False)
        raise a.AccessDenied("Only the person who logged a contact (or an "
                             "admin) can delete it.")
    with _connect() as conn:
        ok = _records.delete(conn, SPEC, contact_id)
    _log(p, "delete contact", existing.student_id, f"contact:{contact_id}")
    return ok


def list_contacts(*, student_id: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  reason: str | None = None, method: str | None = None,
                  contact_with: str | None = None,
                  follow_up_open_only: bool = False,
                  follow_up_overdue_only: bool = False,
                  mine_only: bool = False) -> list[Contact]:
    """Contacts the signed-in user may read, newest first."""
    init_db()
    where, args = [], []
    if date_from:
        where.append("contact_date >= ?")
        args.append(_records.check_date(date_from, "From", ValidationError))
    if date_to:
        where.append("contact_date <= ?")
        args.append(_records.check_date(date_to, "To", ValidationError))
    if follow_up_open_only or follow_up_overdue_only:
        where.append("follow_up_required = 1 AND follow_up_done_on IS NULL")
    if follow_up_overdue_only:
        where.append("follow_up_by IS NOT NULL AND follow_up_by < ?")
        args.append(_records.today())
    p = _access().current()
    if mine_only:
        where.append("recorded_by_user = ?")
        args.append(p.username or "")
    with _connect() as conn:
        rows = _records.select(
            conn, SPEC,
            equals={"student_id": student_id, "reason": reason,
                    "method": method, "contact_with": contact_with},
            where=where, args=args)
    cache: dict[str, bool] = {}
    out = [c for c in rows if _can_read(p, c, cache)]
    _log(p, "list contacts", student_id)
    return out


def contacts_for_student(student_id: str) -> list[Contact]:
    """The student's contact log as the signed-in user may see it
    (newest first) — for the student profile."""
    return list_contacts(student_id=student_id)


# ── Reports ─────────────────────────────────────────────────────────

@dataclass
class ContactSummary:
    date_from: str
    date_to: str
    total: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    by_method: dict[str, int] = field(default_factory=dict)
    by_with: dict[str, int] = field(default_factory=dict)
    incoming: int = 0
    outgoing: int = 0
    students: int = 0
    follow_ups_open: int = 0
    follow_ups_overdue: int = 0
    top_students: list[tuple[str, str, int]] = field(default_factory=list)


def summary(*, date_from: str | None = None,
            date_to: str | None = None) -> ContactSummary:
    """Counts over the contacts the user can see (default: last 30 days)."""
    to = _records.check_date(date_to, "To", ValidationError) \
        or _records.today()
    frm = _records.check_date(date_from, "From", ValidationError) or (
        _dt.date.fromisoformat(to) - _dt.timedelta(days=30)).isoformat()
    if frm > to:
        raise ValidationError("'From' must be on or before 'To'")
    rows = list_contacts(date_from=frm, date_to=to)
    s = ContactSummary(frm, to, total=len(rows))
    per: dict[str, int] = {}
    for c in rows:
        s.by_reason[c.reason] = s.by_reason.get(c.reason, 0) + 1
        s.by_method[c.method] = s.by_method.get(c.method, 0) + 1
        s.by_with[c.contact_with] = s.by_with.get(c.contact_with, 0) + 1
        if c.direction == "Incoming":
            s.incoming += 1
        else:
            s.outgoing += 1
        per[c.student_id] = per.get(c.student_id, 0) + 1
    s.students = len(per)
    open_ = list_contacts(follow_up_open_only=True)
    s.follow_ups_open = len(open_)
    s.follow_ups_overdue = sum(1 for c in open_ if c.follow_up_overdue)
    names = _people.student_names()
    s.top_students = sorted(((sid, names.get(sid, "?"), n)
                             for sid, n in per.items()),
                            key=lambda t: -t[2])[:10]
    return s
