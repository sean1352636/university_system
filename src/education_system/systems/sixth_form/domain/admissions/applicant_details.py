"""What an application holds beyond the form: profile, contacts,
sensitive information and the identity / right-to-study check.

* **Profile** — intake year, sex, ethnicity (ILR codes), nationality,
  first language, residency, and the flags admissions priority and the
  ILR need: LLDD, EHCP, looked after, care leaver, young carer, free
  meals, bursary interest, guaranteed place, and consent to contact the
  previous school / parent agreement. Stored as columns on the applicant
  (``admissions.PROFILE_COLUMNS``) and carried to the student record at
  conversion.
* **Contacts** — parents, carers and emergency contacts
  (``admissions_contacts``), so offers can go to parents and conversion
  has an emergency contact.
* **Sensitive information** (``admissions_sensitive``) — SEND details
  (``send`` capability), medical details (``medical``) and safeguarding
  information handed over by the previous school (``safeguarding``). Each
  field is shown only to the right people and every read and write is in
  the sensitive-access log. Admissions staff see only *that* something is
  held, so they know to involve the DSL/SENCO.
* **Identity / right to study** (``admissions_identity`` plus an
  append-only history) — checked before conversion; the full document
  number is never stored.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_contacts (
    contact_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id             TEXT NOT NULL,
    name                     TEXT NOT NULL,
    relationship             TEXT,
    phone                    TEXT,
    email                    TEXT,
    address                  TEXT,
    is_emergency             INTEGER NOT NULL DEFAULT 0,
    parental_responsibility  INTEGER NOT NULL DEFAULT 0,
    receives_correspondence  INTEGER NOT NULL DEFAULT 1,
    sort_order               INTEGER NOT NULL DEFAULT 0,
    created_at               TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_contact_aid
    ON admissions_contacts(applicant_id);

CREATE TABLE IF NOT EXISTS admissions_sensitive (
    applicant_id              TEXT PRIMARY KEY,
    send_details              TEXT,
    send_updated_by           TEXT,
    send_updated_at           TEXT,
    medical_details           TEXT,
    medical_updated_by        TEXT,
    medical_updated_at        TEXT,
    safeguarding_handover     TEXT,
    safeguarding_received_from TEXT,
    safeguarding_updated_by   TEXT,
    safeguarding_updated_at   TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admissions_identity (
    applicant_id      TEXT PRIMARY KEY,
    document_type     TEXT,
    id_number_last4   TEXT,
    right_to_study    TEXT NOT NULL DEFAULT 'Not yet confirmed',
    visa_type         TEXT,
    visa_expiry       TEXT,
    checked_by        TEXT,
    checked_on        TEXT,
    notes             TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admissions_identity_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id      TEXT NOT NULL,
    at                TEXT NOT NULL DEFAULT (datetime('now')),
    document_type     TEXT,
    id_number_last4   TEXT,
    right_to_study    TEXT,
    visa_type         TEXT,
    visa_expiry       TEXT,
    checked_by        TEXT,
    checked_on        TEXT,
    notes             TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_idh_aid
    ON admissions_identity_history(applicant_id);
"""

# ── Vocabularies ───────────────────────────────────────────────────

#: Same values as the student record, so conversion is a straight copy.
# The same five options as every system's add form; stored lower-case.
from education_system.systems.sixth_form.domain.learners.students.student_profile import (  # noqa: E402
    GENDER_CODES as SEXES,
    GENDER_OPTIONS,
    gender_label,
)

RESIDENCY_STATUSES: tuple[str, ...] = (
    "UK or Irish citizen",
    "EU settled / pre-settled status",
    "Indefinite leave to remain",
    "Refugee or humanitarian protection",
    "Asylum seeker",
    "Visa holder",
    "Other / to be checked",
)
#: Residency that makes a 16–19 learner fundable without further checks.
_FUNDABLE = {"UK or Irish citizen", "EU settled / pre-settled status",
             "Indefinite leave to remain",
             "Refugee or humanitarian protection", "Asylum seeker"}

RIGHT_TO_STUDY: tuple[str, ...] = (
    "Not yet confirmed",
    "Yes - UK or Irish citizen",
    "Yes - settled / pre-settled / ILR",
    "Yes - refugee or asylum seeker",
    "Yes - visa (check expiry)",
    "No",
)
_RIGHT_OK = {r for r in RIGHT_TO_STUDY if r.startswith("Yes")}

CONTACT_RELATIONSHIPS: tuple[str, ...] = (
    "Mother", "Father", "Parent", "Step-parent", "Carer", "Foster carer",
    "Grandparent", "Sibling", "Social worker", "Other relative", "Other",
)

#: Profile fields a person may set, with labels for the timeline.
PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("intake_year", "Intake year"), ("sex", "Sex"),
    ("ethnicity", "Ethnicity"), ("nationality", "Nationality"),
    ("first_language", "First language"),
    ("residency_status", "Residency"),
    ("lldd", "Learning difficulty / disability"), ("ehcp", "EHCP"),
    ("looked_after", "Looked after"), ("care_leaver", "Care leaver"),
    ("young_carer", "Young carer"), ("fsm_eligible", "Free meals eligible"),
    ("bursary_interest", "Bursary interest"),
    ("guaranteed_place", "Guaranteed place"),
    ("consent_contact_school", "Consent to contact previous school"),
    ("parent_consent", "Parent/carer agrees to application"),
)
_PROFILE_LABELS = dict(PROFILE_FIELDS)


def ethnicities() -> tuple[tuple[str, str], ...]:
    from education_system.systems.sixth_form.domain.learners.students import (
        student_profile,
    )
    return student_profile.ETHNICITIES


# ── Schema ─────────────────────────────────────────────────────────

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY = True


def _exists(applicant_id: str) -> bool:
    """Existence check that does not need the admissions capability (the
    DSL/SENCO/medical paths below have their own gates)."""
    init_db()
    with _adm._connect() as conn:
        return conn.execute(
            "SELECT 1 FROM admissions_applicants WHERE applicant_id = ?",
            (applicant_id,)).fetchone() is not None


def _bool(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(v)


# ── Profile ────────────────────────────────────────────────────────

def update_profile(applicant_id: str, **fields: Any) -> _adm.Applicant:
    """Set profile fields (see :data:`PROFILE_FIELDS`). Each change goes
    on the applicant timeline."""
    init_db()
    _guard.require("changing applications")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_archived:
        raise ValidationError(
            f"{applicant_id} is archived; restore it before changing it.")
    unknown = set(fields) - set(_PROFILE_LABELS)
    if unknown:
        raise ValidationError(
            f"Unknown profile field(s): {', '.join(sorted(unknown))}")
    clean: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _adm.FLAG_COLUMNS:
            clean[key] = _bool(value)
            continue
        value = (str(value).strip() if value is not None else "") or None
        if value is None:
            clean[key] = None
        elif key == "intake_year":
            if not re.match(r"^\d{4}/\d{2}$", value):
                raise ValidationError("Intake year must look like '2027/28'")
            clean[key] = value
        elif key == "sex":
            if value.lower() not in SEXES:
                raise ValidationError(f"Sex must be one of: {', '.join(GENDER_OPTIONS)}")
            clean[key] = value.lower()
        elif key == "ethnicity":
            codes = dict(ethnicities())
            code = value if value in codes else next(
                (c for c, label in codes.items() if label == value), None)
            if code is None:
                raise ValidationError("Ethnicity must be one of the ILR codes")
            clean[key] = code
        elif key == "residency_status":
            if value not in RESIDENCY_STATUSES:
                raise ValidationError(
                    f"Residency must be one of: {', '.join(RESIDENCY_STATUSES)}")
            clean[key] = value
        else:
            clean[key] = value
    changes = []
    for key, value in clean.items():
        old = getattr(a, key)
        if (old or None) == (value or None) or (
                key in _adm.FLAG_COLUMNS and bool(old) == value):
            continue
        if key in _adm.FLAG_COLUMNS:
            changes.append(f"{_PROFILE_LABELS[key]}: "
                           f"{'yes' if value else 'no'}")
        else:
            changes.append(f"{_PROFILE_LABELS[key]}: {old or '—'} → "
                           f"{value or '—'}")
    if not changes:
        return a
    _adm._set_profile(applicant_id, event="; ".join(changes), **clean)
    out = _adm.get_applicant(applicant_id)
    assert out is not None
    return out


def funding_eligibility(a: _adm.Applicant) -> str:
    """16–19 funding residency check: "Eligible", "Check residency" or
    "Not recorded" (the ESFA residency rules need a person to confirm
    anything outside the clear cases)."""
    if not a.residency_status:
        return "Not recorded"
    return ("Eligible" if a.residency_status in _FUNDABLE
            else "Check residency")


# ── Contacts ───────────────────────────────────────────────────────

@dataclass
class Contact:
    contact_id: int
    applicant_id: str
    name: str
    relationship: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_emergency: bool
    parental_responsibility: bool
    receives_correspondence: bool
    sort_order: int


def _contact(r: Any) -> Contact:
    return Contact(
        contact_id=r["contact_id"], applicant_id=r["applicant_id"],
        name=r["name"], relationship=r["relationship"], phone=r["phone"],
        email=r["email"], address=r["address"],
        is_emergency=bool(r["is_emergency"]),
        parental_responsibility=bool(r["parental_responsibility"]),
        receives_correspondence=bool(r["receives_correspondence"]),
        sort_order=r["sort_order"])


def _contact_values(data: dict[str, Any]) -> dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Contact name is required")
    rel = (data.get("relationship") or "").strip() or None
    if rel and rel not in CONTACT_RELATIONSHIPS:
        raise ValidationError(
            f"Relationship must be one of: {', '.join(CONTACT_RELATIONSHIPS)}")
    phone = _adm._validate_phone(data.get("phone"))
    email = _adm._validate_email(data.get("email"))
    if not (phone or email):
        raise ValidationError("Give a phone number or e-mail for the contact")
    return {
        "name": name, "relationship": rel, "phone": phone, "email": email,
        "address": (data.get("address") or "").strip() or None,
        "is_emergency": int(_bool(data.get("is_emergency"))),
        "parental_responsibility": int(_bool(
            data.get("parental_responsibility"))),
        "receives_correspondence": int(_bool(
            data.get("receives_correspondence", True))),
    }


def list_contacts(applicant_id: str) -> list[Contact]:
    init_db()
    _guard.require("applicant contacts")
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_contacts WHERE applicant_id = ? "
            "ORDER BY sort_order, contact_id", (applicant_id,)).fetchall()
    return [_contact(r) for r in rows]


def get_contact(contact_id: int) -> Contact | None:
    init_db()
    _guard.require("applicant contacts")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_contacts "
                         "WHERE contact_id = ?", (contact_id,)).fetchone()
    return _contact(r) if r else None


def add_contact(applicant_id: str, data: dict[str, Any]) -> Contact:
    init_db()
    _guard.require("changing applicant contacts")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    v = _contact_values(data)
    with _adm._connect() as conn:
        order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM admissions_contacts "
            "WHERE applicant_id = ?", (applicant_id,)).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO admissions_contacts (applicant_id, name, "
            "relationship, phone, email, address, is_emergency, "
            "parental_responsibility, receives_correspondence, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (applicant_id, v["name"], v["relationship"], v["phone"],
             v["email"], v["address"], v["is_emergency"],
             v["parental_responsibility"], v["receives_correspondence"],
             order))
        _adm._log_event(conn, applicant_id,
                        f"Contact added: {v['name']}"
                        + (f" ({v['relationship']})" if v["relationship"]
                           else ""), kind="contact")
        conn.commit()
        cid = cur.lastrowid
    out = get_contact(cid)
    assert out is not None
    return out


def update_contact(contact_id: int, data: dict[str, Any]) -> Contact:
    init_db()
    _guard.require("changing applicant contacts")
    old = get_contact(contact_id)
    if old is None:
        raise ValidationError(f"No contact #{contact_id}")
    merged = {**old.__dict__, **data}
    v = _contact_values(merged)
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_contacts SET name = ?, relationship = ?, "
            "phone = ?, email = ?, address = ?, is_emergency = ?, "
            "parental_responsibility = ?, receives_correspondence = ? "
            "WHERE contact_id = ?",
            (v["name"], v["relationship"], v["phone"], v["email"],
             v["address"], v["is_emergency"], v["parental_responsibility"],
             v["receives_correspondence"], contact_id))
        _adm._log_event(conn, old.applicant_id,
                        f"Contact updated: {v['name']}", kind="contact")
        conn.commit()
    out = get_contact(contact_id)
    assert out is not None
    return out


def remove_contact(contact_id: int) -> bool:
    init_db()
    _guard.require("changing applicant contacts")
    old = get_contact(contact_id)
    if old is None:
        return False
    with _adm._connect() as conn:
        conn.execute("DELETE FROM admissions_contacts WHERE contact_id = ?",
                     (contact_id,))
        _adm._log_event(conn, old.applicant_id,
                        f"Contact removed: {old.name}", kind="contact")
        conn.commit()
    return True


def correspondence_contacts(applicant_id: str) -> list[Contact]:
    """Parents/carers who should receive letters and e-mails."""
    return [c for c in list_contacts(applicant_id)
            if c.receives_correspondence and c.email]


def emergency_contact(applicant_id: str) -> Contact | None:
    cs = list_contacts(applicant_id)
    return next((c for c in cs if c.is_emergency), cs[0] if cs else None)


# ── Sensitive information ──────────────────────────────────────────

#: area -> (column, capability attribute on access, label)
SENSITIVE_AREAS: dict[str, tuple[str, str, str]] = {
    "send": ("send_details", "SEND", "SEND details"),
    "medical": ("medical_details", "MEDICAL", "Medical details"),
    "safeguarding": ("safeguarding_handover", "SAFEGUARDING",
                     "Safeguarding information from previous school"),
}


@dataclass
class SensitiveView:
    """What the signed-in person may see. ``held`` says which areas have
    something recorded even where the text itself is hidden."""
    applicant_id: str
    held: dict[str, bool]
    visible: dict[str, str | None]
    received_from: str | None = None


def _cap(area: str) -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return getattr(access, SENSITIVE_AREAS[area][1])


def get_sensitive(applicant_id: str) -> SensitiveView:
    """Held/visible sensitive information. Admissions staff see that
    something is held; the text is shown only with the area's capability,
    and each shown area is logged."""
    init_db()
    if not any(_guard.can(_cap(a)) for a in SENSITIVE_AREAS):
        _guard.require("applicant records")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_sensitive "
                         "WHERE applicant_id = ?", (applicant_id,)).fetchone()
    held = {a: bool(r and r[col]) for a, (col, _c, _l) in
            SENSITIVE_AREAS.items()}
    visible: dict[str, str | None] = {}
    for area, (col, _c, _label) in SENSITIVE_AREAS.items():
        if _guard.can(_cap(area)):
            visible[area] = r[col] if r else None
            if held[area]:
                _guard.log_sensitive(f"admissions {area}", "view",
                                     applicant_id=applicant_id)
    return SensitiveView(
        applicant_id=applicant_id, held=held, visible=visible,
        received_from=(r["safeguarding_received_from"]
                       if r and "safeguarding" in visible else None))


def set_sensitive(applicant_id: str, area: str, text: str | None, *,
                  received_from: str | None = None) -> SensitiveView:
    """Record (or clear, with empty text) one area's information. Needs
    that area's capability; the timeline says only that it changed."""
    init_db()
    if area not in SENSITIVE_AREAS:
        raise ValidationError(f"Unknown area {area!r}")
    col, _c, label = SENSITIVE_AREAS[area]
    p = _guard.principal()
    if not p.can(_cap(area)):
        _guard.log_sensitive(f"admissions {area}", "edit",
                             applicant_id=applicant_id, allowed=False)
        p.require(_cap(area), label)
    if not _exists(applicant_id):
        raise ValidationError(f"No applicant {applicant_id!r}")
    text = (text or "").strip() or None
    prefix = col.split("_")[0]
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _adm._connect() as conn:
        conn.execute("INSERT OR IGNORE INTO admissions_sensitive "
                     "(applicant_id) VALUES (?)", (applicant_id,))
        conn.execute(
            f"UPDATE admissions_sensitive SET {col} = ?, "  # noqa: S608 — fixed column map
            f"{prefix}_updated_by = ?, {prefix}_updated_at = ? "
            "WHERE applicant_id = ?",
            (text, _guard.actor(), now, applicant_id))
        if area == "safeguarding" and received_from is not None:
            conn.execute(
                "UPDATE admissions_sensitive SET "
                "safeguarding_received_from = ? WHERE applicant_id = ?",
                ((received_from or "").strip() or None, applicant_id))
        _adm._log_event(conn, applicant_id,
                        f"{label} {'recorded' if text else 'cleared'}",
                        kind="sensitive")
        conn.commit()
    _guard.log_sensitive(f"admissions {area}", "edit",
                         applicant_id=applicant_id)
    return get_sensitive(applicant_id)


def sensitive_for_conversion(applicant_id: str) -> dict[str, str | None]:
    """Raw sensitive text for :func:`conversion.convert_to_student`, which
    hands each area to its own register (SEND, medical, safeguarding).
    Internal: not for display."""
    init_db()
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_sensitive "
                         "WHERE applicant_id = ?", (applicant_id,)).fetchone()
    if r is None:
        return {}
    out = {area: r[col] for area, (col, _c, _l) in SENSITIVE_AREAS.items()}
    out["received_from"] = r["safeguarding_received_from"]
    return out


@dataclass
class DslItem:
    applicant_id: str
    name: str
    status: str
    previous_school: str | None
    reasons: list[str]


def dsl_queue() -> list[DslItem]:
    """Applicants the safeguarding team should look at: a referee asked
    for the DSL to be contacted, or safeguarding information was handed
    over. Needs ``safeguarding``; the list is logged."""
    init_db()
    from education_system.systems.sixth_form.domain.admissions import (
        references as _refs,
    )
    p = _guard.principal()
    if not p.can(_cap("safeguarding")):
        _guard.log_sensitive("admissions safeguarding", "dsl queue",
                             applicant_id="*", allowed=False)
        p.require(_cap("safeguarding"), "the DSL admissions queue")
    _refs.init_db()
    with _adm._connect() as conn:
        rows = conn.execute(
            """SELECT a.applicant_id, a.first_name, a.last_name, a.status,
                      a.previous_school,
                      EXISTS(SELECT 1 FROM admissions_references r
                             WHERE r.applicant_id = a.applicant_id
                               AND r.contact_dsl = 1) AS ref_flag,
                      EXISTS(SELECT 1 FROM admissions_sensitive s
                             WHERE s.applicant_id = a.applicant_id
                               AND s.safeguarding_handover IS NOT NULL)
                          AS handover
                 FROM admissions_applicants a
                WHERE a.archived_at IS NULL
                ORDER BY a.last_name, a.first_name""").fetchall()
    out = []
    for r in rows:
        reasons = []
        if r["ref_flag"]:
            reasons.append("Referee asked for the DSL to be contacted")
        if r["handover"]:
            reasons.append("Safeguarding information from previous school")
        if reasons:
            out.append(DslItem(r["applicant_id"],
                               f"{r['first_name']} {r['last_name']}",
                               r["status"], r["previous_school"], reasons))
    _guard.log_sensitive("admissions safeguarding", "dsl queue",
                         applicant_id="*")
    return out


# ── Identity and right to study ────────────────────────────────────

@dataclass
class IdentityRecord:
    applicant_id: str
    document_type: str | None
    id_number_last4: str | None
    right_to_study: str
    visa_type: str | None
    visa_expiry: str | None
    checked_by: str | None
    checked_on: str | None
    notes: str | None


def get_identity(applicant_id: str) -> IdentityRecord | None:
    init_db()
    _guard.require("applicant identity checks")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_identity "
                         "WHERE applicant_id = ?", (applicant_id,)).fetchone()
    return IdentityRecord(**{k: r[k] for k in r.keys()}) if r else None


def identity_history(applicant_id: str) -> list[dict[str, Any]]:
    init_db()
    _guard.require("applicant identity checks")
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_identity_history WHERE applicant_id = ? "
            "ORDER BY id DESC", (applicant_id,)).fetchall()
    return [dict(r) for r in rows]


def record_identity_check(applicant_id: str, *, document_type: str,
                          document_number: Any, right_to_study: str,
                          visa_type: str | None = None,
                          visa_expiry: str | None = None,
                          checked_on: str | None = None,
                          notes: str | None = None) -> IdentityRecord:
    """Record the ID document seen and the right-to-study outcome. Only
    the last four characters of the number are kept; the previous record
    is kept in the history."""
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as _idc,
    )
    init_db()
    _guard.require("recording identity checks")
    if _adm.get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if document_type not in _idc.ID_DOCUMENT_TYPES:
        raise ValidationError("Document type must be one of: "
                              + ", ".join(_idc.ID_DOCUMENT_TYPES))
    if right_to_study not in RIGHT_TO_STUDY:
        raise ValidationError("Right to study must be one of: "
                              + ", ".join(RIGHT_TO_STUDY))
    try:
        tail = _idc.last4(document_number)
    except _idc.ValidationError as e:
        raise ValidationError(str(e)) from None
    on = _adm._validate_date(checked_on, "Check date") or \
        _dt.date.today().isoformat()
    if on > _dt.date.today().isoformat():
        raise ValidationError("Check date cannot be in the future")
    expiry = _adm._validate_date(visa_expiry, "Visa expiry")
    if right_to_study == "Yes - visa (check expiry)" and not expiry:
        raise ValidationError("Give the visa expiry date")
    who = _guard.actor()
    vals = (document_type, tail, right_to_study,
            (visa_type or "").strip() or None, expiry, who, on,
            (notes or "").strip() or None)
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_identity (applicant_id, document_type, "
            "id_number_last4, right_to_study, visa_type, visa_expiry, "
            "checked_by, checked_on, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(applicant_id) DO UPDATE SET "
            "document_type = excluded.document_type, "
            "id_number_last4 = excluded.id_number_last4, "
            "right_to_study = excluded.right_to_study, "
            "visa_type = excluded.visa_type, visa_expiry = excluded.visa_expiry, "
            "checked_by = excluded.checked_by, checked_on = excluded.checked_on, "
            "notes = excluded.notes", (applicant_id, *vals))
        conn.execute(
            "INSERT INTO admissions_identity_history (applicant_id, "
            "document_type, id_number_last4, right_to_study, visa_type, "
            "visa_expiry, checked_by, checked_on, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (applicant_id, *vals))
        _adm._log_event(conn, applicant_id,
                        f"ID checked ({document_type}): right to study — "
                        f"{right_to_study}", kind="identity")
        conn.commit()
    out = get_identity(applicant_id)
    assert out is not None
    return out


def identity_ok(applicant_id: str, *, on: str | None = None
                ) -> tuple[bool, str]:
    """Whether the applicant can be enrolled on *on* (default today):
    ID seen and right to study confirmed, visa not expired."""
    rec = get_identity(applicant_id)
    if rec is None or not rec.document_type:
        return False, "No ID / right-to-study check recorded"
    if rec.right_to_study not in _RIGHT_OK:
        return False, f"Right to study: {rec.right_to_study}"
    day = on or _dt.date.today().isoformat()
    if rec.visa_expiry and rec.visa_expiry < day:
        return False, f"Visa expired on {rec.visa_expiry}"
    return True, f"Checked {rec.checked_on} by {rec.checked_by or '?'}"


#: Applicant tables this module owns (merge and erasure walk them).
OWNED_TABLES: tuple[str, ...] = (
    "admissions_contacts", "admissions_sensitive", "admissions_identity",
    "admissions_identity_history")
