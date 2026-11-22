"""Parent and carer contacts for pupils.

Each pupil can have several contacts, ordered by priority (1 is called
first). Every contact records whether they hold parental responsibility and
whether they have agreed to receive school e-mail; the e-mail system only
writes to contacts who have.

Staff can read contacts; only :data:`access.PUPIL_EDITORS` can change them,
checked here as well as in the screens. Every change is written to the
activity log (who and which contact, never the details themselves).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

RELATIONSHIPS: tuple[str, ...] = (
    "Mother", "Father", "Carer", "Guardian", "Grandparent", "Social worker", "Other",
)
MAX_PRIORITY = 9

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_contacts (
    contact_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id                INTEGER NOT NULL REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    full_name               TEXT NOT NULL,
    relationship            TEXT NOT NULL,
    priority                INTEGER NOT NULL DEFAULT 1 CHECK (priority BETWEEN 1 AND 9),
    email                   TEXT,
    phone                   TEXT,
    parental_responsibility INTEGER NOT NULL DEFAULT 1 CHECK (parental_responsibility IN (0, 1)),
    receives_email          INTEGER NOT NULL DEFAULT 1 CHECK (receives_email IN (0, 1)),
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    created_by              TEXT,
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by              TEXT
);
CREATE INDEX IF NOT EXISTS ix_pupil_contacts_pupil ON pupil_contacts (pupil_id, priority);
"""

database.register_schema("contacts", _SCHEMA)

#: Simple, deliberately strict address check (also used by the e-mail system).
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Contact:
    contact_id: int
    pupil_id: int
    full_name: str
    relationship: str
    priority: int
    email: str | None
    phone: str | None
    parental_responsibility: bool
    receives_email: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def can_be_emailed(self) -> bool:
        return bool(self.email) and self.receives_email


EDITABLE_FIELDS: tuple[str, ...] = (
    "full_name", "relationship", "priority", "email", "phone",
    "parental_responsibility", "receives_email", "notes",
)
_FIELDS = tuple(f.name for f in fields(Contact))


def valid_email(address: str) -> bool:
    return bool(EMAIL_RE.match(address or "")) and len(address) <= 254


def _bool(value: Any, label: str, problems: list[str]) -> bool:
    if value is None or isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    problems.append(f"{label} must be yes or no")
    return False


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    name = " ".join(str(data.get("full_name") or "").split())[:100]
    if not name:
        problems.append("Contact name is required")
    out["full_name"] = name
    rel = " ".join(str(data.get("relationship") or "").split())
    if rel not in RELATIONSHIPS:
        problems.append(f"Relationship must be one of: {', '.join(RELATIONSHIPS)}")
    out["relationship"] = rel
    try:
        priority = int(data.get("priority") or 1)
    except (TypeError, ValueError):
        priority = 0
    if not 1 <= priority <= MAX_PRIORITY:
        problems.append(f"Priority must be a number from 1 to {MAX_PRIORITY}")
    out["priority"] = priority
    email = str(data.get("email") or "").strip().lower() or None
    if email and not valid_email(email):
        problems.append("E-mail address doesn't look right")
    out["email"] = email
    phone = " ".join(str(data.get("phone") or "").split()) or None
    if phone and not _PHONE_RE.match(phone):
        problems.append("Phone number doesn't look right")
    out["phone"] = phone
    if not email and not phone:
        problems.append("Give an e-mail address or a phone number")
    out["parental_responsibility"] = _bool(
        data.get("parental_responsibility", True), "Parental responsibility", problems)
    out["receives_email"] = _bool(data.get("receives_email", True),
                                  "Receives school e-mail", problems)
    notes = str(data.get("notes") or "").strip()[:1000]
    out["notes"] = notes or None
    if problems:
        raise ValidationError(problems)
    return out


def validate(data: dict[str, Any]) -> dict[str, Any]:
    """Check contact details without saving them (Add Pupil checks the
    parent/carer before the pupil is created)."""
    return _validate(data)


def _row(r) -> Contact:
    values = {k: r[k] for k in _FIELDS}
    values["parental_responsibility"] = bool(values["parental_responsibility"])
    values["receives_email"] = bool(values["receives_email"])
    return Contact(**values)


def _require_editor(actor: Principal, action: str, target: str) -> None:
    if not actor.can_edit_pupils:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view contacts but not change them.")


def _pupil_or_raise(pupil_id: int) -> P.Pupil:
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    return pupil


# ── Read ─────────────────────────────────────────────────────────────

def list_for_pupil(pupil_id: int) -> list[Contact]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM pupil_contacts WHERE pupil_id = ? ORDER BY priority, contact_id",
            (int(pupil_id),)).fetchall()
    return [_row(r) for r in rows]


def get_contact(contact_id: int) -> Contact | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_contacts WHERE contact_id = ?",
                         (int(contact_id),)).fetchone()
    return _row(r) if r else None


def emailable_for_pupils(pupil_ids: list[int]) -> dict[int, list[Contact]]:
    """Contacts with an address who accept school e-mail, per pupil."""
    if not pupil_ids:
        return {}
    out: dict[int, list[Contact]] = {int(p): [] for p in pupil_ids}
    with database.connect() as conn:
        for start in range(0, len(pupil_ids), 500):
            chunk = [int(p) for p in pupil_ids[start:start + 500]]
            rows = conn.execute(
                f"SELECT * FROM pupil_contacts WHERE pupil_id IN "
                f"({', '.join('?' for _ in chunk)}) AND email IS NOT NULL "
                f"AND receives_email = 1 ORDER BY pupil_id, priority", chunk).fetchall()
            for r in rows:
                out[r["pupil_id"]].append(_row(r))
    return out


# ── Write ────────────────────────────────────────────────────────────

def add_contact(pupil_id: int, data: dict[str, Any], *, actor: Principal) -> Contact:
    pupil = _pupil_or_raise(pupil_id)
    _require_editor(actor, "contact.create", pupil.admission_no)
    try:
        clean = _validate(data)
    except ValidationError as e:
        activity_log.record("contact.create", target=pupil.admission_no, outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    cols = list(clean)
    with database.connect() as conn:
        cur = conn.execute(
            f"INSERT INTO pupil_contacts (pupil_id, {', '.join(cols)}, created_by, updated_by) "
            f"VALUES (?, {', '.join('?' for _ in cols)}, ?, ?)",
            [pupil.pupil_id] + [int(v) if isinstance(v, bool) else v for v in clean.values()]
            + [actor.username, actor.username])
        contact_id = cur.lastrowid
    activity_log.record("contact.create", target=pupil.admission_no, principal=actor,
                        contact=contact_id)
    _portal_sync(contact_id, actor)
    return get_contact(contact_id)  # type: ignore[return-value]


def update_contact(contact_id: int, changes: dict[str, Any], *, actor: Principal) -> Contact:
    current = get_contact(contact_id)
    if current is None:
        raise NotFound(f"No contact with id {contact_id}")
    pupil = _pupil_or_raise(current.pupil_id)
    _require_editor(actor, "contact.update", pupil.admission_no)
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS}
    merged.update(changes)
    try:
        clean = _validate(merged)
    except ValidationError as e:
        activity_log.record("contact.update", target=pupil.admission_no, outcome="invalid",
                            principal=actor, contact=contact_id, problems=len(e.problems))
        raise
    changed = sorted(k for k, v in clean.items() if getattr(current, k) != v)
    if changed:
        with database.connect() as conn:
            conn.execute(
                f"UPDATE pupil_contacts SET {', '.join(f'{k} = ?' for k in clean)}, "
                "updated_at = datetime('now'), updated_by = ? WHERE contact_id = ?",
                [int(v) if isinstance(v, bool) else v for v in clean.values()]
                + [actor.username, contact_id])
    activity_log.record("contact.update", target=pupil.admission_no, principal=actor,
                        contact=contact_id, outcome="ok" if changed else "no_change",
                        fields=changed or None)
    if changed:
        _portal_sync(contact_id, actor)
    return get_contact(contact_id)  # type: ignore[return-value]


def delete_contact(contact_id: int, *, actor: Principal) -> Contact:
    current = get_contact(contact_id)
    if current is None:
        raise NotFound(f"No contact with id {contact_id}")
    pupil = _pupil_or_raise(current.pupil_id)
    _require_editor(actor, "contact.delete", pupil.admission_no)
    # Before the delete: the link's contact_id is cleared by the foreign key.
    from education_system.systems.secondary.modules.portals.domain import portal_accounts
    portal_accounts.contact_removed(contact_id, actor=actor)
    with database.connect() as conn:
        conn.execute("DELETE FROM pupil_contacts WHERE contact_id = ?", (contact_id,))
    activity_log.record("contact.delete", target=pupil.admission_no, principal=actor,
                        contact=contact_id)
    return current


def _portal_sync(contact_id: int, actor: Principal) -> None:
    """Keep the parent portal login and link in step with the contact (never
    stops the contact change; e-mails are queued, not delivered)."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts
    portal_accounts.contact_hook(contact_id, actor=actor)
