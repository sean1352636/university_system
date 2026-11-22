"""Feeder-school references: request → sent → (chased) → received.

The applicant row only ever held a referee name/contact and a status
word. ``admissions_references`` holds the whole workflow, one row per
reference requested:

* the referee (name, role, school, email, phone);
* the request: requested date, date sent, due date, every chase (count
  and last date);
* the reference itself once received: attendance %, predicted GCSEs
  (also recorded as Predicted GCSE rows for the applicant), behaviour
  rating and comment, academic comment, and the received date;
* a single safeguarding/SEND flag — "please contact the DSL". It is a
  yes/no only: **no safeguarding or SEND detail is stored here**. The
  referee is asked to speak to the college's Designated Safeguarding
  Lead directly; conversion adds a "contact the DSL" onboarding task.

The applicant's older ``reference_status`` field follows this tracker:
every change here re-derives it (Not requested / Requested / Received /
Declined — see :func:`tracker_status`), and once an applicant has
tracked references ``admissions.set_reference_status`` refuses a
hand-set value that disagrees, so the two cannot drift apart.

Writes need the ``admissions`` capability. Requests and chases can be
e-mailed to the referee through :mod:`admissions_comms` (``send=True``)
or only recorded (the default — for a letter or phone call).
"""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

STATUSES: tuple[str, ...] = ("Requested", "Sent", "Chased", "Received",
                             "Declined", "Cancelled")
OPEN_STATUSES: tuple[str, ...] = ("Requested", "Sent", "Chased")
BEHAVIOUR_RATINGS: tuple[str, ...] = (
    "Excellent", "Good", "Satisfactory", "Some concerns", "Serious concerns",
)
#: Days after sending before a reference counts as overdue when no due
#: date was set, and the gap between chases.
DEFAULT_DUE_DAYS: int = 14
CHASE_INTERVAL_DAYS: int = 7

#: Applicant.reference_status for each workflow status.
_APPLICANT_STATUS = {
    "Requested": "Requested", "Sent": "Requested", "Chased": "Requested",
    "Received": "Received", "Declined": "Declined",
    "Cancelled": "Not requested",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_references (
    reference_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id     TEXT NOT NULL,
    referee_name     TEXT NOT NULL,
    referee_role     TEXT,
    referee_school   TEXT,
    referee_email    TEXT,
    referee_phone    TEXT,
    status           TEXT NOT NULL DEFAULT 'Requested',
    requested_on     TEXT NOT NULL,
    requested_by     TEXT,
    sent_on          TEXT,
    due_date         TEXT,
    chase_count      INTEGER NOT NULL DEFAULT 0,
    last_chased_on   TEXT,
    received_on      TEXT,
    attendance_pct   REAL,
    predicted_gcses  TEXT,
    behaviour        TEXT,
    behaviour_comment TEXT,
    academic_comment TEXT,
    contact_dsl      INTEGER NOT NULL DEFAULT 0,
    recorded_by      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_ref_aid ON admissions_references(applicant_id);
CREATE INDEX IF NOT EXISTS idx_adm_ref_st  ON admissions_references(status);
"""


@dataclass
class Reference:
    reference_id: int
    applicant_id: str
    referee_name: str
    referee_role: str | None
    referee_school: str | None
    referee_email: str | None
    referee_phone: str | None
    status: str
    requested_on: str
    requested_by: str | None
    sent_on: str | None
    due_date: str | None
    chase_count: int
    last_chased_on: str | None
    received_on: str | None
    attendance_pct: float | None
    predicted_gcses: str | None
    behaviour: str | None
    behaviour_comment: str | None
    academic_comment: str | None
    contact_dsl: bool
    recorded_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def effective_due(self) -> str | None:
        if self.due_date:
            return self.due_date
        base = self.sent_on or self.requested_on
        try:
            return (_dt.date.fromisoformat(base[:10])
                    + _dt.timedelta(days=DEFAULT_DUE_DAYS)).isoformat()
        except (TypeError, ValueError):
            return None

    @property
    def is_overdue(self) -> bool:
        due = self.effective_due
        return bool(self.is_open and due
                    and due < _dt.date.today().isoformat())

    @property
    def chase_due(self) -> bool:
        """Overdue and not chased in the last CHASE_INTERVAL_DAYS."""
        if not self.is_overdue:
            return False
        if not self.last_chased_on:
            return True
        try:
            last = _dt.date.fromisoformat(self.last_chased_on[:10])
        except ValueError:
            return True
        return (_dt.date.today() - last).days >= CHASE_INTERVAL_DAYS


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    return _adm._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row(r: db.Row) -> Reference:
    d = {k: r[k] for k in r.keys()}
    d["contact_dsl"] = bool(d["contact_dsl"])
    return Reference(**d)


def _today() -> str:
    return _dt.date.today().isoformat()


def _username() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def _text(value: Any, label: str, *, required: bool = False,
          max_len: int = 200) -> str | None:
    s = str(value).strip() if value not in (None, "") else ""
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if len(s) > max_len:
        raise ValidationError(f"{label} is too long (max {max_len})")
    return s


def _derive(statuses: list[str]) -> str | None:
    """The applicant-level status for these tracker statuses (None when
    there are no tracked references)."""
    if not statuses:
        return None
    if "Received" in statuses:
        return "Received"
    if any(s in OPEN_STATUSES for s in statuses):
        return "Requested"
    if "Declined" in statuses:
        return "Declined"
    return "Not requested"


def _tracker_status(conn: db.Connection, applicant_id: str) -> str | None:
    rows = conn.execute(
        "SELECT status FROM admissions_references WHERE applicant_id = ?",
        (applicant_id,)).fetchall()
    return _derive([r["status"] for r in rows])


def tracker_status(applicant_id: str) -> str | None:
    """What the applicant's ``reference_status`` must be according to
    the tracker, or None when no reference is tracked (the hand-set value
    then stands)."""
    init_db()
    with _connect() as conn:
        return _tracker_status(conn, applicant_id)


def _sync_applicant(conn: db.Connection, applicant_id: str) -> None:
    """Mirror the most advanced reference status onto the applicant.
    With no tracked references the hand-set value is left alone."""
    status = _tracker_status(conn, applicant_id)
    if status is None:
        return
    old = conn.execute(
        "SELECT reference_status FROM admissions_applicants "
        "WHERE applicant_id = ?", (applicant_id,)).fetchone()
    if old and old["reference_status"] != status:
        conn.execute(
            "UPDATE admissions_applicants SET reference_status = ?, "
            "updated_at = datetime('now') WHERE applicant_id = ?",
            (status, applicant_id))
        _adm._log_event(conn, applicant_id,
                        f"Reference: {old['reference_status']} → {status}",
                        kind="reference")


def sync_reference_status(applicant_id: str | None = None) -> int:
    """Re-derive ``reference_status`` from the tracker for one applicant
    (or every applicant with tracked references). Returns how many were
    corrected."""
    init_db()
    _guard.require("changing applications")
    with _connect() as conn:
        if applicant_id:
            ids = [applicant_id]
        else:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT applicant_id FROM admissions_references"
            ).fetchall()]
        fixed = 0
        for aid in ids:
            want = _tracker_status(conn, aid)
            row = conn.execute(
                "SELECT reference_status FROM admissions_applicants "
                "WHERE applicant_id = ?", (aid,)).fetchone()
            if want is not None and row and row["reference_status"] != want:
                _sync_applicant(conn, aid)
                fixed += 1
        conn.commit()
    return fixed


# ── Reads ──────────────────────────────────────────────────────────

def get_reference(reference_id: int) -> Reference | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM admissions_references "
                         "WHERE reference_id = ?", (int(reference_id),)
                         ).fetchone()
    return _row(r) if r else None


def list_references(*, applicant_id: str | None = None,
                    status: str | None = None, open_only: bool = False,
                    overdue_only: bool = False) -> list[Reference]:
    init_db()
    clauses, args = [], []
    if applicant_id:
        clauses.append("applicant_id = ?")
        args.append(applicant_id)
    if status:
        if status not in STATUSES:
            raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only or overdue_only:
        clauses.append(f"status IN ({','.join('?' * len(OPEN_STATUSES))})")
        args.extend(OPEN_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(
            f"SELECT * FROM admissions_references {where} "
            "ORDER BY requested_on DESC, reference_id DESC", args).fetchall()]
    if overdue_only:
        rows = [r for r in rows if r.is_overdue]
    return rows


def chase_list() -> list[Reference]:
    """Open references that are overdue and due a chase."""
    return [r for r in list_references(open_only=True) if r.chase_due]


def dsl_contact_requested(applicant_id: str) -> bool:
    """Whether any received reference asks the college to contact the DSL."""
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM admissions_references WHERE applicant_id = ? "
            "AND contact_dsl = 1 LIMIT 1", (applicant_id,)).fetchone() is not None


def dsl_flagged_applicants() -> list[str]:
    """Applicant ids whose referee asked for DSL contact (flag only)."""
    init_db()
    with _connect() as conn:
        return [r["applicant_id"] for r in conn.execute(
            "SELECT DISTINCT applicant_id FROM admissions_references "
            "WHERE contact_dsl = 1 ORDER BY applicant_id").fetchall()]


# ── Workflow ───────────────────────────────────────────────────────

def request_reference(applicant_id: str, *, referee_name: str,
                      referee_role: str | None = None,
                      referee_school: str | None = None,
                      referee_email: str | None = None,
                      referee_phone: str | None = None,
                      due_date: str | None = None,
                      requested_by: str | None = None,
                      notes: str | None = None,
                      send: bool = False) -> Reference:
    """Start a reference request for an applicant. With ``send`` the
    request is e-mailed to the referee straight away (which also marks
    it Sent); otherwise it is only recorded."""
    init_db()
    _guard.require("requesting references")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    name = _text(referee_name, "Referee name", required=True, max_len=120)
    email = _adm._validate_email(referee_email)
    phone = _adm._validate_phone(referee_phone)
    if not (email or phone):
        raise ValidationError("The referee's email or phone is required")
    due = _adm._validate_date(due_date, "Due date")
    by = requested_by or _username()
    school = _text(referee_school, "School", max_len=120) or a.previous_school
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO admissions_references
                   (applicant_id, referee_name, referee_role, referee_school,
                    referee_email, referee_phone, status, requested_on,
                    requested_by, due_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'Requested', ?, ?, ?, ?)""",
            (applicant_id, name, _text(referee_role, "Role", max_len=80),
             school, email, phone, _today(), by, due,
             _text(notes, "Notes", max_len=1000)))
        # Keep the legacy referee columns filled for older screens.
        conn.execute(
            "UPDATE admissions_applicants SET reference_name = ?, "
            "reference_contact = ? WHERE applicant_id = ?",
            (name, email or phone, applicant_id))
        _adm._log_event(conn, applicant_id,
                        f"Reference requested from {name}"
                        + (f" ({school})" if school else ""),
                        kind="reference")
        _sync_applicant(conn, applicant_id)
        conn.commit()
        rid = cur.lastrowid
    if send:
        send_request(rid)
    out = get_reference(rid)
    assert out is not None
    return out


def send_request(reference_id: int):
    """E-mail the request to the referee through the outbox; returns the
    queued message (see :func:`admissions_comms.send_reference_request`)."""
    from education_system.systems.sixth_form.domain.admissions import (
        admissions_comms,
    )
    return admissions_comms.send_reference_request(reference_id)


def adopt_legacy_reference(applicant_id: str) -> Reference:
    """Start the workflow from the referee already on the applicant."""
    _guard.require("requesting references")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if not a.reference_name:
        raise ValidationError("The applicant has no referee recorded")
    contact = a.reference_contact or ""
    email = contact if "@" in contact else None
    phone = None if email else (contact or None)
    return request_reference(applicant_id, referee_name=a.reference_name,
                             referee_email=email, referee_phone=phone,
                             notes="Started from the referee on the "
                                   "application")


def _update(reference_id: int, event: str, **cols: Any) -> Reference:
    _guard.require("changing references")
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    sets = ", ".join(f"{k} = ?" for k in cols)
    with _connect() as conn:
        conn.execute(
            f"UPDATE admissions_references SET {sets}, "
            "updated_at = datetime('now') WHERE reference_id = ?",
            (*cols.values(), reference_id))
        _adm._log_event(conn, ref.applicant_id, event, kind="reference")
        _sync_applicant(conn, ref.applicant_id)
        conn.commit()
    out = get_reference(reference_id)
    assert out is not None
    return out


def mark_sent(reference_id: int, *, sent_on: str | None = None,
              due_date: str | None = None) -> Reference:
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    if ref.status not in ("Requested", "Sent"):
        raise ValidationError(f"Reference is {ref.status} — cannot mark sent")
    sent = _adm._validate_date(sent_on, "Sent on") or _today()
    due = _adm._validate_date(due_date, "Due date") or ref.due_date or (
        _dt.date.fromisoformat(sent)
        + _dt.timedelta(days=DEFAULT_DUE_DAYS)).isoformat()
    return _update(reference_id, f"Reference request sent to "
                                 f"{ref.referee_name} (due {due})",
                   status="Sent", sent_on=sent, due_date=due)


def chase(reference_id: int, *, send: bool = False) -> Reference:
    """Record a chase. With ``send`` the reminder is e-mailed to the
    referee first (:func:`admissions_comms.send_reference_chase`, which
    records the chase itself)."""
    _guard.require("chasing references")
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    if not ref.is_open:
        raise ValidationError(f"Reference is {ref.status} — nothing to chase")
    if send:
        from education_system.systems.sixth_form.domain.admissions import (
            admissions_comms,
        )
        admissions_comms.send_reference_chase(reference_id)
        out = get_reference(reference_id)
        assert out is not None
        return out
    return _update(reference_id,
                   f"Reference chased ({ref.chase_count + 1}) — "
                   f"{ref.referee_name}",
                   status="Chased", chase_count=ref.chase_count + 1,
                   last_chased_on=_today(),
                   sent_on=ref.sent_on or _today())


def record_received(reference_id: int, *,
                    received_on: str | None = None,
                    attendance_pct: Any = None,
                    predicted_gcses: str | None = None,
                    behaviour: str | None = None,
                    behaviour_comment: str | None = None,
                    academic_comment: str | None = None,
                    contact_dsl: bool = False,
                    recorded_by: str | None = None,
                    record_predictions: bool = True) -> Reference:
    """Record the reference content.

    ``contact_dsl`` is the referee's "please contact the DSL" request —
    a flag only; do not put safeguarding or SEND detail in any comment.
    ``predicted_gcses`` (e.g. "Maths 7, English 6") is also recorded as
    Predicted GCSE rows when ``record_predictions`` is True.
    """
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    if ref.status in ("Declined", "Cancelled"):
        raise ValidationError(f"Reference is {ref.status}")
    rec = _adm._validate_date(received_on, "Received on") or _today()
    att = None
    if attendance_pct not in (None, ""):
        try:
            att = round(float(str(attendance_pct).rstrip("%")), 1)
        except (TypeError, ValueError):
            raise ValidationError("Attendance must be a percentage") from None
        if not 0 <= att <= 100:
            raise ValidationError("Attendance must be between 0 and 100")
    if behaviour and behaviour not in BEHAVIOUR_RATINGS:
        raise ValidationError(f"Behaviour must be one of: "
                              f"{', '.join(BEHAVIOUR_RATINGS)}")
    by = recorded_by or _username()
    out = _update(
        reference_id,
        f"Reference received from {ref.referee_name}"
        + (" — referee asks admissions to contact the DSL"
           if contact_dsl else ""),
        status="Received", received_on=rec, attendance_pct=att,
        predicted_gcses=_text(predicted_gcses, "Predicted GCSEs",
                              max_len=500),
        behaviour=behaviour or None,
        behaviour_comment=_text(behaviour_comment, "Behaviour comment",
                                max_len=2000),
        academic_comment=_text(academic_comment, "Academic comment",
                               max_len=2000),
        contact_dsl=1 if contact_dsl else 0, recorded_by=by)
    if record_predictions and predicted_gcses:
        from education_system.systems.sixth_form.domain.admissions import (
            entry_requirements as _er,
        )
        for subj, grade in _er.parse_gcse_text(predicted_gcses):
            try:
                _er.record_gcse(ref.applicant_id, subj, grade,
                                result_type="Predicted", source="Reference",
                                entered_by=by)
            except ValidationError:
                logger.warning("Reference #%d: could not record predicted "
                               "%s %s", reference_id, subj, grade)
    return out


def decline(reference_id: int, *, notes: str | None = None) -> Reference:
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    return _update(reference_id,
                   f"Referee {ref.referee_name} declined to give a reference",
                   status="Declined",
                   notes=_text(notes, "Notes", max_len=1000) or ref.notes)


def cancel(reference_id: int) -> Reference:
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    return _update(reference_id, "Reference request cancelled",
                   status="Cancelled")


def update_referee(reference_id: int, **fields: Any) -> Reference:
    """Correct the referee's details or the due date."""
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    cols: dict[str, Any] = {}
    if "referee_name" in fields:
        cols["referee_name"] = _text(fields["referee_name"], "Referee name",
                                     required=True, max_len=120)
    if "referee_role" in fields:
        cols["referee_role"] = _text(fields["referee_role"], "Role", max_len=80)
    if "referee_school" in fields:
        cols["referee_school"] = _text(fields["referee_school"], "School",
                                       max_len=120)
    if "referee_email" in fields:
        cols["referee_email"] = _adm._validate_email(fields["referee_email"])
    if "referee_phone" in fields:
        cols["referee_phone"] = _adm._validate_phone(fields["referee_phone"])
    if "due_date" in fields:
        cols["due_date"] = _adm._validate_date(fields["due_date"], "Due date")
    if "notes" in fields:
        cols["notes"] = _text(fields["notes"], "Notes", max_len=1000)
    if not cols:
        return ref
    return _update(reference_id, "Referee details updated", **cols)


# ── Letters ────────────────────────────────────────────────────────

def render_request(reference_id: int) -> tuple[str, str]:
    """(subject, body) of the reference request to the referee."""
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    a = _adm.get_applicant(ref.applicant_id)
    name = a.full_name if a else ref.applicant_id
    dob = f" (date of birth {a.dob})" if a and a.dob else ""
    due = ref.effective_due or "as soon as you can"
    body = (
        f"Dear {ref.referee_name},\n\n"
        f"{name}{dob} has applied to join our Sixth Form and has named "
        f"you as their referee.\n\nPlease could you let us have, by {due}:\n"
        "  • their attendance this year (%)\n"
        "  • predicted GCSE grades for each subject\n"
        "  • a short comment on behaviour and attitude to learning\n"
        "  • a short academic comment\n\n"
        "If there is any safeguarding or SEND information we should know "
        "before enrolment, please do not include it in the reference — "
        "just tell us, and our Designated Safeguarding Lead will contact "
        "you directly.\n\n"
        f"Our reference: {ref.applicant_id}/{ref.reference_id}\n\n"
        "Thank you,\nAdmissions Team")
    return f"Reference request — {name}", body


def render_chase(reference_id: int) -> tuple[str, str]:
    ref = get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    a = _adm.get_applicant(ref.applicant_id)
    name = a.full_name if a else ref.applicant_id
    sent = ref.sent_on or ref.requested_on
    body = (f"Dear {ref.referee_name},\n\nWe wrote on {sent} asking for a "
            f"reference for {name}. We have not received it yet — could you "
            "send it as soon as possible?\n\n"
            f"Our reference: {ref.applicant_id}/{ref.reference_id}\n\n"
            "Thank you,\nAdmissions Team")
    return f"Reminder: reference for {name}", body


def summary() -> dict[str, int]:
    rows = list_references()
    out = {s: 0 for s in STATUSES}
    for r in rows:
        out[r.status] = out.get(r.status, 0) + 1
    out["Overdue"] = sum(1 for r in rows if r.is_overdue)
    out["DSL flags"] = sum(1 for r in rows if r.contact_dsl)
    return out
