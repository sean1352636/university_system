"""Trusted contacts — consent to contact someone a student trusts when
there is serious concern about their safety or wellbeing.

Follows *Suicide-safer universities* and the UUK guidance on sharing
information with trusted contacts (2022):

* **The student chooses.** They nominate up to :data:`MAX_CONTACTS` people
  and give (or withdraw) consent for the university to contact them when
  there is serious concern for their safety or wellbeing. Every change of
  consent is kept (:func:`consent_history`).
* **Each use is a decision, recorded.** Staff record why a contact is
  needed (:func:`request_use`), a second person approves it
  (:func:`decide_use` — a safeguarding lead, health administrator or
  administrator, never the person asking), and the contact itself is
  recorded (:func:`record_contact`).
* **Emergencies.** Where there is a risk to life, the contact may be made
  straight away — with consent, or without it on the basis of the student's
  vital interests — and approved afterwards.
* **The student is told afterwards** (:func:`inform_student`), unless telling
  them now would increase the risk, in which case that decision and a date
  to review it are recorded (:func:`defer_informing`).

A student manages their own contacts and consent and sees each use once
they have been told about it. Support staff see a student's contacts and
the log; each look is audited (and refused if the audit fails).
"""

from __future__ import annotations

from datetime import date, datetime

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
    schema,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import wellbeing_bus

MAX_CONTACTS = 3
CONSENT_STATEMENT = (
    "I agree that the university may contact the people I have named here if it is "
    "seriously concerned about my safety or wellbeing. I understand that the university "
    "will only share what is needed, will record each time it does so, and will normally "
    "tell me afterwards.")
BASES = ("consent", "vital_interests")
METHODS = ("phone", "email", "in person", "video call", "letter")
STATUSES = ("requested", "approved", "declined", "contacted")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(action, actor, **details) -> None:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    try:
        log_activity(action, "trusted_contact", user=access.username(actor), details=details)
    except Exception:
        pass


def _reading():
    conn = get_connection()
    schema.ensure_trusted_contacts(conn)
    return conn


def _target(actor, student_id=None) -> str:
    """The student acted on: a student acts on themselves; staff name one."""
    scoped = access.support_scope(actor)
    if scoped is not None:
        if student_id not in (None, "") and str(student_id) != scoped:
            raise PermissionError("You can only manage your own trusted contacts.")
        return scoped
    if student_id in (None, ""):
        raise ValueError("Choose a student.")
    return str(student_id)


def _clean_contact(name, relationship, phone, email) -> tuple:
    name = str(name or "").strip()
    phone = str(phone or "").strip()
    email = str(email or "").strip()
    if len(name) < 2:
        raise ValueError("Give the contact's name.")
    if not phone and not email:
        raise ValueError("Give a phone number or an e-mail address for the contact.")
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise ValueError("That e-mail address doesn't look right.")
    digits = [c for c in phone if c.isdigit()]
    if phone and len(digits) < 7:
        raise ValueError("That phone number doesn't look right.")
    return name, str(relationship or "").strip() or None, phone or None, email or None


# ------------------------------------------------------------------ contacts

def list_contacts(actor, student_id=None, *, include_removed=False) -> list[dict]:
    sid = _target(actor, student_id)
    staff = access.support_scope(actor) is None
    if staff:
        access.record_view(actor, "trusted_contacts", student_id=sid)
    conn = _reading()
    try:
        sql = "SELECT * FROM trusted_contacts WHERE student_id = ?"
        if not include_removed:
            sql += " AND is_active = 1"
        return [dict(r) for r in conn.execute(sql + " ORDER BY priority, contact_id", (sid,))]
    finally:
        conn.close()


def add_contact(actor, name, relationship, phone=None, email=None, *, address=None,
                student_id=None, priority=None) -> int:
    sid = _target(actor, student_id)
    name, relationship, phone, email = _clean_contact(name, relationship, phone, email)
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        if not conn.execute("SELECT 1 FROM students WHERE student_id = ?", (sid,)).fetchone():
            raise ValueError(f"No student {sid}.")
        count = conn.execute("SELECT COUNT(*) FROM trusted_contacts WHERE student_id = ? "
                             "AND is_active = 1", (sid,)).fetchone()[0]
        if count >= MAX_CONTACTS:
            raise ValueError(f"You can name up to {MAX_CONTACTS} trusted contacts; remove "
                             "one first.")
        contact_id = conn.execute(
            "INSERT INTO trusted_contacts (student_id, name, relationship, phone, email, "
            "address, priority, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, name, relationship, phone, email, (address or "").strip() or None,
             int(priority or count + 1), access.username(actor))).lastrowid
    _log("add", actor, student_id=sid, contact_id=contact_id)
    return int(contact_id)


def update_contact(actor, contact_id, name, relationship, phone=None, email=None, *,
                   address=None, priority=None) -> None:
    contact = _contact(contact_id)
    _target(actor, contact["student_id"])
    name, relationship, phone, email = _clean_contact(name, relationship, phone, email)
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        conn.execute(
            "UPDATE trusted_contacts SET name = ?, relationship = ?, phone = ?, email = ?, "
            "address = ?, priority = COALESCE(?, priority), updated_at = ? "
            "WHERE contact_id = ? AND is_active = 1",
            (name, relationship, phone, email, (address or "").strip() or None,
             None if priority in (None, "") else int(priority), _now(), int(contact_id)))
    _log("update", actor, student_id=contact["student_id"], contact_id=contact_id)


def remove_contact(actor, contact_id, reason="Removed by the student") -> None:
    """A soft removal: the contact stays in the log of past uses."""
    contact = _contact(contact_id)
    _target(actor, contact["student_id"])
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        conn.execute("UPDATE trusted_contacts SET is_active = 0, removed_reason = ?, "
                     "updated_at = ? WHERE contact_id = ?",
                     (str(reason or "").strip() or None, _now(), int(contact_id)))
    _log("remove", actor, student_id=contact["student_id"], contact_id=contact_id)


def _contact(contact_id) -> dict:
    conn = _reading()
    try:
        row = conn.execute("SELECT * FROM trusted_contacts WHERE contact_id = ?",
                           (int(contact_id),)).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"Trusted contact #{contact_id} was not found.")
    return dict(row)


# ------------------------------------------------------------------ consent

def consent(actor, student_id=None) -> dict:
    """``{'consent_given': bool, 'given_at', 'withdrawn_at', 'statement'}``."""
    sid = _target(actor, student_id)
    conn = _reading()
    try:
        row = conn.execute("SELECT * FROM trusted_contact_consents WHERE student_id = ?",
                           (sid,)).fetchone()
    finally:
        conn.close()
    out = dict(row) if row else {"student_id": sid, "consent_given": 0, "given_at": None,
                                 "withdrawn_at": None, "statement": None}
    out["consent_given"] = bool(out.get("consent_given"))
    return out


def set_consent(actor, given: bool, *, student_id=None) -> None:
    """Give or withdraw consent. Only the student gives it (staff may record
    a withdrawal the student asks for in person); consent needs at least one
    contact."""
    sid = _target(actor, student_id)
    is_student = access.support_scope(actor) is not None
    if given and not is_student:
        raise PermissionError("Only the student can give consent to contact their "
                              "trusted contacts.")
    now = _now()
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        if given and not conn.execute("SELECT 1 FROM trusted_contacts WHERE student_id = ? "
                                      "AND is_active = 1", (sid,)).fetchone():
            raise ValueError("Add a trusted contact before giving consent.")
        conn.execute(
            "INSERT INTO trusted_contact_consents (student_id, consent_given, statement, "
            "recorded_by, given_at, withdrawn_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(student_id) DO UPDATE SET consent_given = excluded.consent_given, "
            "statement = COALESCE(excluded.statement, statement), recorded_by = "
            "excluded.recorded_by, given_at = COALESCE(excluded.given_at, given_at), "
            "withdrawn_at = excluded.withdrawn_at, updated_at = excluded.updated_at",
            (sid, int(bool(given)), CONSENT_STATEMENT if given else None,
             access.username(actor), now if given else None, None if given else now, now))
        conn.execute("INSERT INTO trusted_contact_consent_history (student_id, action, "
                     "statement, by_user) VALUES (?, ?, ?, ?)",
                     (sid, "given" if given else "withdrawn",
                      CONSENT_STATEMENT if given else None, access.username(actor)))
    _log("consent_given" if given else "consent_withdrawn", actor, student_id=sid)


def consent_history(actor, student_id=None) -> list[dict]:
    sid = _target(actor, student_id)
    conn = _reading()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM trusted_contact_consent_history WHERE student_id = ? ORDER BY id DESC",
            (sid,))]
    finally:
        conn.close()


# ------------------------------------------------------------------ uses

def request_use(actor, student_id, contact_id, reason, circumstances="", *,
                emergency=False) -> int:
    """Record that a contact is needed. Without consent it may be made only
    in an emergency (risk to life), on the student's vital interests."""
    access.require_support_staff(actor)
    reason = str(reason or "").strip()
    if len(reason) < 15:
        raise ValueError("Explain the serious concern (at least a sentence).")
    contact = _contact(contact_id)
    if contact["student_id"] != str(student_id) or not contact["is_active"]:
        raise ValueError("That is not one of this student's current trusted contacts.")
    given = _consent_given(str(student_id))
    if not given and not emergency:
        raise ValueError("The student has not consented. Without consent a contact may be "
                         "made only in an emergency where there is a risk to life.")
    basis = "consent" if given else "vital_interests"
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        use_id = conn.execute(
            "INSERT INTO trusted_contact_uses (student_id, contact_id, reason, circumstances, "
            "basis, emergency, status, requested_by) VALUES (?, ?, ?, ?, ?, ?, 'requested', ?)",
            (str(student_id), int(contact_id), reason,
             wellbeing_bus.seal_text(str(circumstances).strip()) if circumstances else None,
             basis, int(bool(emergency)), access.username(actor))).lastrowid
    _log("request_use", actor, student_id=student_id, use_id=use_id, basis=basis,
         emergency=bool(emergency))
    return int(use_id)


def _consent_given(student_id) -> bool:
    conn = _reading()
    try:
        row = conn.execute("SELECT consent_given FROM trusted_contact_consents "
                           "WHERE student_id = ?", (student_id,)).fetchone()
    finally:
        conn.close()
    return bool(row and row[0])


def _use(conn, use_id) -> dict:
    row = conn.execute("SELECT * FROM trusted_contact_uses WHERE use_id = ?",
                       (int(use_id),)).fetchone()
    if not row:
        raise ValueError(f"Contact record #{use_id} was not found.")
    return dict(row)


def decide_use(actor, use_id, approve: bool, note="") -> None:
    """Approve or decline a use. The approver must hold an approver role and
    must not be the person who asked."""
    access.require_support_staff(actor)
    if not access.may_approve_contact_use(actor):
        raise PermissionError("Only a safeguarding lead, health administrator or "
                              "administrator can approve contacting a trusted contact.")
    me = access.username(actor)
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        use = _use(conn, use_id)
        if use["requested_by"] == me:
            raise PermissionError("Someone other than the person asking must approve it.")
        if use["approved_at"]:
            raise ValueError("This has already been decided.")
        if not approve and use["status"] == "contacted":
            raise ValueError("The contact has already been made; record approval or "
                             "concerns about it in the note.")
        status = use["status"] if use["status"] == "contacted" else (
            "approved" if approve else "declined")
        conn.execute("UPDATE trusted_contact_uses SET status = ?, approved_by = ?, "
                     "approved_at = ?, approval_note = ? WHERE use_id = ?",
                     (status, me, _now(), str(note or "").strip() or None, int(use_id)))
    _log("approve_use" if approve else "decline_use", actor, use_id=use_id)


def record_contact(actor, use_id, method, outcome, *, contacted_at=None) -> None:
    """Record the contact made: approved first, unless it was an emergency."""
    access.require_support_staff(actor)
    if method not in METHODS:
        raise ValueError(f"Method must be one of: {', '.join(METHODS)}.")
    outcome = str(outcome or "").strip()
    if len(outcome) < 5:
        raise ValueError("Record what was said and agreed.")
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        use = _use(conn, use_id)
        if use["status"] == "declined":
            raise ValueError("This contact was declined.")
        if use["status"] == "contacted":
            raise ValueError("The contact has already been recorded.")
        if use["status"] != "approved" and not use["emergency"]:
            raise ValueError("It needs approval before the contact is made (or mark it an "
                             "emergency when it is requested).")
        conn.execute("UPDATE trusted_contact_uses SET status = 'contacted', contacted_by = ?, "
                     "contacted_at = ?, method = ?, outcome = ? WHERE use_id = ?",
                     (access.username(actor), contacted_at or _now(), method, outcome,
                      int(use_id)))
    _log("contacted", actor, use_id=use_id, method=method)


def inform_student(actor, use_id, message="") -> None:
    """Tell the student who was contacted, when and why (their inbox)."""
    access.require_support_staff(actor)
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        use = _use(conn, use_id)
        if use["status"] != "contacted":
            raise ValueError("Record the contact before telling the student about it.")
        if use["student_informed"]:
            raise ValueError("The student has already been told.")
        contact = conn.execute("SELECT name, relationship FROM trusted_contacts WHERE "
                               "contact_id = ?", (use["contact_id"],)).fetchone()
        conn.execute("UPDATE trusted_contact_uses SET student_informed = 1, informed_at = ?, "
                     "informed_by = ?, inform_deferred_reason = NULL, inform_review_date = NULL "
                     "WHERE use_id = ?", (_now(), access.username(actor), int(use_id)))
    who = contact[0] if contact else "your trusted contact"
    if contact and contact[1]:
        who += f" ({contact[1]})"
    body = (f"On {str(use['contacted_at'])[:16]} the university contacted {who}, one of your "
            f"trusted contacts, by {use['method']}.\n\nWhy: {use['reason']}\n\n"
            + (f"{str(message).strip()}\n\n" if str(message or "").strip() else "")
            + "You can see this under Wellbeing Casework → Trusted Contacts, change your "
              "contacts or withdraw your consent at any time. Student support is here if you "
              "would like to talk about it.")
    wellbeing_bus.notify_inbox(use["student_id"], "We contacted your trusted contact", body)
    _log("informed", actor, use_id=use_id)


def defer_informing(actor, use_id, reason, review_date) -> None:
    """Record a decision not to tell the student yet, with a review date."""
    access.require_support_staff(actor)
    reason = str(reason or "").strip()
    if len(reason) < 15:
        raise ValueError("Explain why telling the student now would increase the risk.")
    try:
        review = date.fromisoformat(str(review_date).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError("Give a review date (YYYY-MM-DD).") from None
    with transaction() as conn:
        schema.ensure_trusted_contacts(conn)
        use = _use(conn, use_id)
        if use["student_informed"]:
            raise ValueError("The student has already been told.")
        conn.execute("UPDATE trusted_contact_uses SET inform_deferred_reason = ?, "
                     "inform_review_date = ? WHERE use_id = ?", (reason, review, int(use_id)))
    _log("inform_deferred", actor, use_id=use_id)


def uses(actor, student_id=None) -> list[dict]:
    """The log of uses. Staff see everything (audited); a student sees the
    uses they have been told about, without staff notes."""
    sid = _target(actor, student_id)
    staff = access.support_scope(actor) is None
    if staff:
        access.record_view(actor, "trusted_contact_uses", student_id=sid)
    conn = _reading()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT u.*, c.name AS contact_name, c.relationship FROM trusted_contact_uses u "
            "JOIN trusted_contacts c ON c.contact_id = u.contact_id WHERE u.student_id = ? "
            "ORDER BY u.use_id DESC", (sid,))]
    finally:
        conn.close()
    if staff:
        for row in rows:
            row["circumstances"] = wellbeing_bus.reveal(row.get("circumstances"))
        return rows
    keep = ("use_id", "contact_name", "relationship", "reason", "method", "contacted_at",
            "informed_at", "basis")
    return [{k: r.get(k) for k in keep} for r in rows if r["student_informed"]]


def work_queue(actor) -> dict:
    """Staff follow-up: uses awaiting approval, approved but not yet made,
    and made but the student not yet told (deferrals due for review first)."""
    access.require_support_staff(actor)
    conn = _reading()
    try:
        def q(where):
            return [dict(r) for r in conn.execute(
                "SELECT u.use_id, u.student_id, u.status, u.emergency, u.basis, u.reason, "
                "u.requested_by, u.requested_at, u.contacted_at, u.inform_review_date, "
                "c.name AS contact_name FROM trusted_contact_uses u JOIN trusted_contacts c "
                f"ON c.contact_id = u.contact_id WHERE {where} "  # nosec B608 - literals
                "ORDER BY u.use_id")]
        return {
            "awaiting_approval": q("u.approved_at IS NULL AND u.status IN "
                                   "('requested', 'contacted')"),
            "approved_not_contacted": q("u.status = 'approved'"),
            "student_not_told": q("u.status = 'contacted' AND u.student_informed = 0 AND "
                                  "(u.inform_review_date IS NULL OR "
                                  "u.inform_review_date <= date('now'))"),
            "told_later": q("u.status = 'contacted' AND u.student_informed = 0 AND "
                            "u.inform_review_date > date('now')"),
        }
    finally:
        conn.close()
