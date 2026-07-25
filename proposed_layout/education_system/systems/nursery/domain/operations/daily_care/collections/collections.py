"""Domain layer for Collections & Late Pickup (Nursery System).

Two tables covering the two halves of getting a child home safely:

* ``authorised_collectors`` — the vetted list of people allowed to collect a
  child, each with an optional **collection password** (stored only as a salted
  PBKDF2 hash, never in the clear), a validity window and a revoke switch.
  ``verify_collector`` is the door check: is this person on the list, in date,
  and did they give the right password?
* ``late_collections`` — the uncollected-child log: the booked due time, when
  the child was actually collected, the late fee that follows from the
  setting's policy, and how far staff had to escalate. EYFS requires a written
  procedure for uncollected children and evidence it was followed.

Authorisation deliberately also honours the ``emergency_contacts.can_collect``
flag, so contacts already marked as collectors there don't have to be re-keyed.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``collections_cli.py``, Tk GUI in ``collections_views.py``.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import logging
import math
import random
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Collections & Late Pickup"
CATEGORY = "Daily Care & Routines"

COLLECTOR_PREFIX = "NAC"
LATE_PREFIX = "NLC"
ID_DIGITS = 3

RELATIONSHIPS = (
    "Parent", "Grandparent", "Aunt/Uncle", "Sibling (over 16)",
    "Family friend", "Neighbour", "Childminder", "Nanny", "Other",
)

COLLECTOR_STATUSES = ("active", "revoked")

# The escalation ladder a setting works through when nobody arrives. Order
# matters — ``suggested_escalation`` walks it by how late the collection is.
ESCALATION_STAGES = (
    "none",
    "parent-called",
    "emergency-contacts-called",
    "manager-informed",
    "dsl-informed",
    "local-authority",
)

FEE_STATUSES = ("due", "invoiced", "paid", "waived")

# Late-collection fee policy. Most settings charge per started block after a
# short grace period; these are the defaults and are applied by ``compute_fee``.
LATE_FEE_GRACE_MINUTES = 5
LATE_FEE_BLOCK_MINUTES = 15
LATE_FEE_PER_BLOCK = 5.0

# How late (in minutes) each escalation stage kicks in.
_ESCALATION_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (0, "none"),
    (1, "parent-called"),
    (30, "emergency-contacts-called"),
    (60, "manager-informed"),
    (90, "dsl-informed"),
    (120, "local-authority"),
)

_PBKDF2_ITERATIONS = 120_000
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")


class ValidationError(ValueError):
    """Raised for invalid collector / late-collection input."""


@dataclass
class Collector:
    collector_id: str
    pupil_id: str
    full_name: str
    relationship: str | None
    phone: str | None
    has_password: bool
    photo_on_file: bool
    id_checked: bool
    is_escalation_contact: bool
    valid_from: str | None
    valid_until: str | None
    status: str
    notes: str | None
    child_name: str | None = None

    def in_date(self, day: str | None = None) -> bool:
        day = day or _dt.date.today().isoformat()
        if self.valid_from and day < self.valid_from:
            return False
        if self.valid_until and day > self.valid_until:
            return False
        return True

    def authorised(self, day: str | None = None) -> bool:
        return self.status == "active" and self.in_date(day)


@dataclass
class LateCollection:
    record_id: str
    pupil_id: str
    event_date: str
    due_time: str
    collected_time: str | None
    minutes_late: int
    collected_by: str | None
    collector_id: str | None
    fee_amount: float
    fee_status: str
    escalation_stage: str
    escalated_to: str | None
    parent_contacted: bool
    safeguarding_referral: bool
    recorded_by: str | None
    notes: str | None
    child_name: str | None = None
    recorded_by_name: str | None = None

    @property
    def outstanding(self) -> float:
        return self.fee_amount if self.fee_status in ("due", "invoiced") else 0.0


@dataclass
class CollectionCheck:
    """The result of checking someone at the door."""

    allowed: bool
    reason: str
    collector: Collector | None = None
    password_required: bool = False


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for collections")
        raise


# ── Collection passwords ─────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Salted PBKDF2 hash of a collection password, safe to store."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                 _PBKDF2_ITERATIONS)
    return "$".join((
        "pbkdf2_sha256", str(_PBKDF2_ITERATIONS),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ))


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of a password against a stored hash."""
    if not stored:
        return False
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64),
            int(iterations))
    except (ValueError, TypeError):
        logger.warning("Malformed collection password hash — treating as no match")
        return False
    return hmac.compare_digest(candidate, expected)


# ── Fee & escalation policy ──────────────────────────────────────────────────

def compute_fee(minutes_late: int,
                *, grace: int = LATE_FEE_GRACE_MINUTES,
                block: int = LATE_FEE_BLOCK_MINUTES,
                per_block: float = LATE_FEE_PER_BLOCK) -> float:
    """Late fee for ``minutes_late``: per started block after the grace period."""
    chargeable = minutes_late - grace
    if chargeable <= 0:
        return 0.0
    return round(math.ceil(chargeable / block) * per_block, 2)


def suggested_escalation(minutes_late: int) -> str:
    """The escalation stage the setting should have reached by now."""
    stage = "none"
    for threshold, name in _ESCALATION_THRESHOLDS:
        if minutes_late >= threshold:
            stage = name
    return stage


def minutes_between(due_time: str, collected_time: str) -> int:
    """Whole minutes from ``due_time`` to ``collected_time`` (never negative)."""
    due = _dt.datetime.strptime(due_time, "%H:%M")
    got = _dt.datetime.strptime(collected_time, "%H:%M")
    return max(int((got - due).total_seconds() // 60), 0)


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    # ``value or ""`` would swallow a legitimate 0 (0 minutes late, a £0 fee),
    # so test for None explicitly.
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(value)


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _check_time(value: Any, label: str, *, required: bool = False) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _TIME_RE.match(v):
        raise ValidationError(f"{label} must be HH:MM")
    if int(v[:2]) > 23 or int(v[3:]) > 59:
        raise ValidationError(f"{label} is not a real time")
    return v


def _generate_id(table: str, column: str, prefix: str) -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                f"SELECT {column} FROM {table}").fetchall()}  # noqa: S608
    except sqlite3.Error:
        logger.exception("Could not read existing ids from %s", table)
        raise
    seq = 1
    while f"{prefix}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{prefix}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{prefix}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError(f"Could not allocate a unique id for {table}")


def generate_collector_id() -> str:
    return _generate_id("authorised_collectors", "collector_id", COLLECTOR_PREFIX)


def generate_late_id() -> str:
    return _generate_id("late_collections", "record_id", LATE_PREFIX)


# ── Authorised collectors ────────────────────────────────────────────────────

_COLLECTOR_SELECT = """
SELECT c.*, TRIM(p.first_name || ' ' || p.last_name) AS child_name
FROM authorised_collectors c
LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
"""


def _collector_row(r: sqlite3.Row) -> Collector:
    keys = r.keys()
    return Collector(
        collector_id=r["collector_id"], pupil_id=r["pupil_id"],
        full_name=r["full_name"], relationship=r["relationship"],
        phone=r["phone"], has_password=bool(r["password_hash"]),
        photo_on_file=bool(r["photo_on_file"]),
        id_checked=bool(r["id_checked"]),
        is_escalation_contact=bool(r["is_escalation_contact"]),
        valid_from=r["valid_from"], valid_until=r["valid_until"],
        status=r["status"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
    )


def list_collectors(*, pupil_id: str | None = None,
                    status: str | None = None) -> list[Collector]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("c.pupil_id = ?")
        params.append(pupil_id)
    if status:
        clauses.append("c.status = ?")
        params.append(status)
    sql = _COLLECTOR_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY child_name, c.is_escalation_contact DESC, c.full_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_collectors failed")
        raise
    return [_collector_row(r) for r in rows]


def get_collector(collector_id: str) -> Collector | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_COLLECTOR_SELECT + " WHERE c.collector_id = ?",
                               (collector_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_collector(%s) failed", collector_id)
        raise
    return _collector_row(row) if row else None


def _validate_collector(data: dict[str, Any], *,
                        require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = _opt(data.get("pupil_id"))
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    name = _opt(data.get("full_name"))
    if not name:
        raise ValidationError("Collector name is required")
    out["full_name"] = name
    out["relationship"] = _opt(data.get("relationship"))
    phone = _opt(data.get("phone"))
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Phone must be 6–20 digits / spaces / + ( ) -")
    out["phone"] = phone
    out["photo_on_file"] = _as_bool(data.get("photo_on_file"))
    out["id_checked"] = _as_bool(data.get("id_checked"))
    out["is_escalation_contact"] = _as_bool(data.get("is_escalation_contact"))
    out["valid_from"] = _check_date(data.get("valid_from"), "Valid from",
                                    required=False)
    out["valid_until"] = _check_date(data.get("valid_until"), "Valid until",
                                     required=False)
    if (out["valid_from"] and out["valid_until"]
            and out["valid_until"] < out["valid_from"]):
        raise ValidationError("'Valid until' cannot be before 'valid from'")
    status = (str(data.get("status") or "active").strip().lower())
    if status not in COLLECTOR_STATUSES:
        raise ValidationError("Status must be one of: "
                              + ", ".join(COLLECTOR_STATUSES))
    out["status"] = status
    out["notes"] = _opt(data.get("notes"))
    return out


def _password_value(data: dict[str, Any], existing: Collector | None,
                    conn: sqlite3.Connection | None = None) -> str | None:
    """Resolve the password_hash column from a form payload.

    A blank password field means "leave whatever is stored alone"; the explicit
    ``clear_password`` flag removes it.
    """
    if _as_bool(data.get("clear_password")):
        return None
    raw = _opt(data.get("password"))
    if raw:
        if len(raw) < 4:
            raise ValidationError("Collection password must be at least 4 characters")
        return hash_password(raw)
    if existing is None or conn is None:
        return None
    row = conn.execute(
        "SELECT password_hash FROM authorised_collectors WHERE collector_id = ?",
        (existing.collector_id,)).fetchone()
    return row["password_hash"] if row else None


def create_collector(data: dict[str, Any]) -> Collector:
    """Add someone to a child's authorised-collector list."""
    _ensure_schema()
    payload = _validate_collector(data)
    cid = generate_collector_id()
    pw_hash = _password_value(data, None)
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO authorised_collectors (
                    collector_id, pupil_id, full_name, relationship, phone,
                    password_hash, photo_on_file, id_checked,
                    is_escalation_contact, valid_from, valid_until, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["full_name"],
                 payload["relationship"], payload["phone"], pw_hash,
                 int(payload["photo_on_file"]), int(payload["id_checked"]),
                 int(payload["is_escalation_contact"]), payload["valid_from"],
                 payload["valid_until"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for authorised collector %s", cid)
        raise ValidationError(f"Could not add collector — {e}") from e
    c = get_collector(cid)
    assert c is not None
    logger.info("Added authorised collector %s for pupil %s",
                cid, payload["pupil_id"])
    return c


def update_collector(collector_id: str, data: dict[str, Any]) -> Collector:
    _ensure_schema()
    existing = get_collector(collector_id)
    if existing is None:
        raise ValidationError(f"No collector with id {collector_id}")
    payload = _validate_collector(data, require_pupil=False)
    try:
        with connect() as conn:
            pw_hash = _password_value(data, existing, conn)
            conn.execute(
                """
                UPDATE authorised_collectors SET
                    full_name = ?, relationship = ?, phone = ?,
                    password_hash = ?, photo_on_file = ?, id_checked = ?,
                    is_escalation_contact = ?, valid_from = ?, valid_until = ?,
                    status = ?, notes = ?
                WHERE collector_id = ?
                """,
                (payload["full_name"], payload["relationship"], payload["phone"],
                 pw_hash, int(payload["photo_on_file"]),
                 int(payload["id_checked"]),
                 int(payload["is_escalation_contact"]), payload["valid_from"],
                 payload["valid_until"], payload["status"], payload["notes"],
                 collector_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for authorised collector %s", collector_id)
        raise
    c = get_collector(collector_id)
    assert c is not None
    logger.info("Updated authorised collector %s", collector_id)
    return c


def set_collection_password(collector_id: str, password: str) -> Collector:
    """Set or replace a collector's spoken collection password."""
    return update_collector(collector_id, {
        **_collector_as_fields(collector_id), "password": password})


def revoke_collector(collector_id: str, reason: str | None = None) -> Collector:
    """Withdraw someone's authorisation without deleting the audit trail."""
    _ensure_schema()
    existing = get_collector(collector_id)
    if existing is None:
        raise ValidationError(f"No collector with id {collector_id}")
    note = existing.notes or ""
    if reason:
        note = f"{note}\nRevoked: {reason}".strip()
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE authorised_collectors SET status = 'revoked', notes = ? "
                "WHERE collector_id = ?", (note, collector_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not revoke collector %s", collector_id)
        raise
    c = get_collector(collector_id)
    assert c is not None
    logger.info("Revoked authorised collector %s", collector_id)
    return c


def delete_collector(collector_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM authorised_collectors WHERE collector_id = ?",
                (collector_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting collector %s", collector_id)
        raise
    if deleted:
        logger.info("Deleted authorised collector %s", collector_id)
    return deleted


def _collector_as_fields(collector_id: str) -> dict[str, Any]:
    c = get_collector(collector_id)
    if c is None:
        raise ValidationError(f"No collector with id {collector_id}")
    return {
        "full_name": c.full_name, "relationship": c.relationship,
        "phone": c.phone, "photo_on_file": c.photo_on_file,
        "id_checked": c.id_checked,
        "is_escalation_contact": c.is_escalation_contact,
        "valid_from": c.valid_from, "valid_until": c.valid_until,
        "status": c.status, "notes": c.notes,
    }


# ── The door check ───────────────────────────────────────────────────────────

def emergency_contact_collectors(pupil_id: str) -> list[str]:
    """Names from ``emergency_contacts`` already flagged as able to collect."""
    _ensure_schema()
    try:
        with connect() as conn:
            return [r[0] for r in conn.execute(
                "SELECT full_name FROM emergency_contacts "
                "WHERE pupil_id = ? AND can_collect = 1", (pupil_id,)).fetchall()]
    except sqlite3.Error:
        logger.exception("emergency_contact_collectors(%s) failed", pupil_id)
        return []


def verify_collector(pupil_id: str, person_name: str,
                     password: str | None = None,
                     *, on_day: str | None = None) -> CollectionCheck:
    """Check someone at the door: on the list, in date, right password?

    Never raises for an unknown person — it returns a refusing
    ``CollectionCheck`` so the caller can show the reason to staff.
    """
    _ensure_schema()
    name = _opt(person_name)
    if not name:
        return CollectionCheck(False, "No collector name given.")
    day = on_day or _today()

    matches = [c for c in list_collectors(pupil_id=pupil_id)
               if c.full_name.strip().lower() == name.lower()]
    if not matches:
        if any(n.strip().lower() == name.lower()
               for n in emergency_contact_collectors(pupil_id)):
            return CollectionCheck(
                True,
                f"{name} is an emergency contact marked as able to collect. "
                "Add them to the authorised list to record ID and a password.")
        return CollectionCheck(
            False, f"{name} is NOT on this child's authorised collector list.")

    collector = matches[0]
    if collector.status == "revoked":
        return CollectionCheck(
            False, f"{name}'s authorisation has been revoked.", collector)
    if not collector.in_date(day):
        window = f"{collector.valid_from or '…'} to {collector.valid_until or '…'}"
        return CollectionCheck(
            False, f"{name} is only authorised {window}.", collector)

    if collector.has_password:
        if password is None:
            return CollectionCheck(
                False, f"{name} must give their collection password.",
                collector, password_required=True)
        try:
            with connect() as conn:
                row = conn.execute(
                    "SELECT password_hash FROM authorised_collectors "
                    "WHERE collector_id = ?", (collector.collector_id,)).fetchone()
        except sqlite3.Error:
            logger.exception("Could not read collection password for %s",
                             collector.collector_id)
            raise
        if not verify_password(password, row["password_hash"] if row else None):
            logger.warning("Wrong collection password given for %s (pupil %s)",
                           collector.collector_id, pupil_id)
            return CollectionCheck(
                False, "Collection password does not match.", collector,
                password_required=True)

    checks = []
    if not collector.id_checked:
        checks.append("photo ID not yet verified")
    if not collector.photo_on_file:
        checks.append("no photo on file")
    suffix = f" ({'; '.join(checks)})" if checks else ""
    return CollectionCheck(True, f"{name} is authorised to collect{suffix}.",
                           collector)


# ── Late collections ─────────────────────────────────────────────────────────

_LATE_SELECT = """
SELECT l.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(st.first_name || ' ' || st.last_name) AS recorded_by_name
FROM late_collections l
LEFT JOIN pupils p ON p.pupil_id = l.pupil_id
LEFT JOIN staff st ON st.staff_id = l.recorded_by
"""


def _late_row(r: sqlite3.Row) -> LateCollection:
    keys = r.keys()
    return LateCollection(
        record_id=r["record_id"], pupil_id=r["pupil_id"],
        event_date=r["event_date"], due_time=r["due_time"],
        collected_time=r["collected_time"],
        minutes_late=int(r["minutes_late"]), collected_by=r["collected_by"],
        collector_id=r["collector_id"], fee_amount=float(r["fee_amount"]),
        fee_status=r["fee_status"], escalation_stage=r["escalation_stage"],
        escalated_to=r["escalated_to"],
        parent_contacted=bool(r["parent_contacted"]),
        safeguarding_referral=bool(r["safeguarding_referral"]),
        recorded_by=r["recorded_by"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        recorded_by_name=(
            r["recorded_by_name"] if "recorded_by_name" in keys else None),
    )


def list_late_collections(*, pupil_id: str | None = None,
                          event_date: str | None = None,
                          date_from: str | None = None,
                          date_to: str | None = None,
                          fee_status: str | None = None
                          ) -> list[LateCollection]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("l.pupil_id = ?")
        params.append(pupil_id)
    if event_date:
        clauses.append("l.event_date = ?")
        params.append(event_date)
    if date_from:
        clauses.append("l.event_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("l.event_date <= ?")
        params.append(date_to)
    if fee_status:
        clauses.append("l.fee_status = ?")
        params.append(fee_status)
    sql = _LATE_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY l.event_date DESC, l.due_time DESC, l.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_late_collections failed")
        raise
    return [_late_row(r) for r in rows]


def get_late_collection(record_id: str) -> LateCollection | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_LATE_SELECT + " WHERE l.record_id = ?",
                               (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_late_collection(%s) failed", record_id)
        raise
    return _late_row(row) if row else None


def _validate_late(data: dict[str, Any], *,
                   require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = _opt(data.get("pupil_id"))
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    out["event_date"] = _check_date(data.get("event_date") or _today(), "Date")
    out["due_time"] = _check_time(data.get("due_time"), "Due time", required=True)
    out["collected_time"] = _check_time(data.get("collected_time"),
                                        "Collected time")

    minutes = _opt(data.get("minutes_late"))
    if minutes is not None:
        try:
            out["minutes_late"] = max(int(minutes), 0)
        except ValueError as e:
            raise ValidationError("Minutes late must be a whole number") from e
    elif out["collected_time"]:
        out["minutes_late"] = minutes_between(out["due_time"],
                                              out["collected_time"])
    else:
        out["minutes_late"] = 0

    out["collected_by"] = _opt(data.get("collected_by"))
    out["collector_id"] = _opt(data.get("collector_id"))

    fee = _opt(data.get("fee_amount"))
    if fee is None:
        out["fee_amount"] = compute_fee(out["minutes_late"])
    else:
        try:
            out["fee_amount"] = round(float(fee), 2)
        except ValueError as e:
            raise ValidationError("Fee must be a number") from e
        if out["fee_amount"] < 0:
            raise ValidationError("Fee cannot be negative")

    fee_status = str(data.get("fee_status") or "due").strip().lower()
    if fee_status not in FEE_STATUSES:
        raise ValidationError("Fee status must be one of: "
                              + ", ".join(FEE_STATUSES))
    out["fee_status"] = fee_status

    stage = _opt(data.get("escalation_stage"))
    if stage is None:
        stage = suggested_escalation(out["minutes_late"])
    stage = stage.strip().lower()
    if stage not in ESCALATION_STAGES:
        raise ValidationError("Escalation stage must be one of: "
                              + ", ".join(ESCALATION_STAGES))
    out["escalation_stage"] = stage

    out["escalated_to"] = _opt(data.get("escalated_to"))
    out["parent_contacted"] = _as_bool(data.get("parent_contacted"))
    out["safeguarding_referral"] = _as_bool(data.get("safeguarding_referral"))
    out["recorded_by"] = _opt(data.get("recorded_by"))
    out["notes"] = _opt(data.get("notes"))
    return out


def log_late_collection(data: dict[str, Any]) -> LateCollection:
    """Record an uncollected / late-collected child.

    ``minutes_late``, the fee and the escalation stage are all derived from the
    due and collected times when not given explicitly.
    """
    _ensure_schema()
    payload = _validate_late(data)
    rid = generate_late_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO late_collections (
                    record_id, pupil_id, event_date, due_time, collected_time,
                    minutes_late, collected_by, collector_id, fee_amount,
                    fee_status, escalation_stage, escalated_to,
                    parent_contacted, safeguarding_referral, recorded_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["event_date"],
                 payload["due_time"], payload["collected_time"],
                 payload["minutes_late"], payload["collected_by"],
                 payload["collector_id"], payload["fee_amount"],
                 payload["fee_status"], payload["escalation_stage"],
                 payload["escalated_to"], int(payload["parent_contacted"]),
                 int(payload["safeguarding_referral"]), payload["recorded_by"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for late collection %s", rid)
        raise ValidationError(f"Could not log late collection — {e}") from e
    rec = get_late_collection(rid)
    assert rec is not None
    logger.info("Logged late collection %s for pupil %s (%s min late)",
                rid, payload["pupil_id"], payload["minutes_late"])
    return rec


def update_late_collection(record_id: str,
                           data: dict[str, Any]) -> LateCollection:
    _ensure_schema()
    if get_late_collection(record_id) is None:
        raise ValidationError(f"No late collection with id {record_id}")
    payload = _validate_late(data, require_pupil=False)
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE late_collections SET
                    event_date = ?, due_time = ?, collected_time = ?,
                    minutes_late = ?, collected_by = ?, collector_id = ?,
                    fee_amount = ?, fee_status = ?, escalation_stage = ?,
                    escalated_to = ?, parent_contacted = ?,
                    safeguarding_referral = ?, recorded_by = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["event_date"], payload["due_time"],
                 payload["collected_time"], payload["minutes_late"],
                 payload["collected_by"], payload["collector_id"],
                 payload["fee_amount"], payload["fee_status"],
                 payload["escalation_stage"], payload["escalated_to"],
                 int(payload["parent_contacted"]),
                 int(payload["safeguarding_referral"]), payload["recorded_by"],
                 payload["notes"], record_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("UPDATE failed for late collection %s", record_id)
        raise
    rec = get_late_collection(record_id)
    assert rec is not None
    logger.info("Updated late collection %s", record_id)
    return rec


def close_late_collection(record_id: str, collected_time: str | None = None,
                          collected_by: str | None = None) -> LateCollection:
    """Stamp the child as collected, recomputing minutes late and the fee."""
    rec = get_late_collection(record_id)
    if rec is None:
        raise ValidationError(f"No late collection with id {record_id}")
    when = _check_time(collected_time or _now(), "Collected time", required=True)
    assert when is not None
    minutes = minutes_between(rec.due_time, when)
    return update_late_collection(record_id, {
        "event_date": rec.event_date, "due_time": rec.due_time,
        "collected_time": when, "minutes_late": minutes,
        "collected_by": collected_by or rec.collected_by,
        "collector_id": rec.collector_id,
        "fee_amount": compute_fee(minutes),
        "fee_status": rec.fee_status,
        "escalation_stage": rec.escalation_stage,
        "escalated_to": rec.escalated_to,
        "parent_contacted": rec.parent_contacted,
        "safeguarding_referral": rec.safeguarding_referral,
        "recorded_by": rec.recorded_by, "notes": rec.notes,
    })


def waive_fee(record_id: str, reason: str | None = None) -> LateCollection:
    """Write the late fee off (goodwill, setting error, agreed with parent)."""
    rec = get_late_collection(record_id)
    if rec is None:
        raise ValidationError(f"No late collection with id {record_id}")
    notes = rec.notes or ""
    if reason:
        notes = f"{notes}\nFee waived: {reason}".strip()
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE late_collections SET fee_status = 'waived', notes = ? "
                "WHERE record_id = ?", (notes, record_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not waive fee on late collection %s", record_id)
        raise
    out = get_late_collection(record_id)
    assert out is not None
    logger.info("Waived late fee on %s", record_id)
    return out


def delete_late_collection(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM late_collections WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting late collection %s", record_id)
        raise
    if deleted:
        logger.info("Deleted late collection %s", record_id)
    return deleted


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"],
             f"{r['first_name']} {r['last_name']} ({r['staff_id']})"
             + (f" — {r['role']}" if r["role"] else ""))
            for r in rows]


def children_without_collectors() -> list[tuple[str, str]]:
    """Active children with nobody authorised to collect them — a real gap."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT p.pupil_id, TRIM(p.first_name || ' ' || p.last_name) "
                "FROM pupils p WHERE p.status = 'active' AND p.pupil_id NOT IN ("
                "  SELECT pupil_id FROM authorised_collectors "
                "  WHERE status = 'active') AND p.pupil_id NOT IN ("
                "  SELECT pupil_id FROM emergency_contacts WHERE can_collect = 1)"
                " ORDER BY p.last_name, p.first_name").fetchall()
    except sqlite3.Error:
        logger.exception("children_without_collectors failed")
        raise
    return [(r[0], r[1]) for r in rows]


def summary(day: str | None = None) -> dict[str, Any]:
    """Headline counts for the collections board."""
    day = _check_date(day or _today(), "Date")
    assert day is not None
    collectors = list_collectors()
    late = list_late_collections()
    this_month = [r for r in late if r.event_date[:7] == day[:7]]
    return {
        "date": day,
        "collectors": len(collectors),
        "active_collectors": sum(1 for c in collectors if c.authorised(day)),
        "revoked_collectors": sum(1 for c in collectors if c.status == "revoked"),
        "with_password": sum(1 for c in collectors if c.has_password),
        "id_unchecked": sum(1 for c in collectors
                            if c.status == "active" and not c.id_checked),
        "children_without_collectors": len(children_without_collectors()),
        "late_today": sum(1 for r in late if r.event_date == day),
        "late_this_month": len(this_month),
        "open_late": sum(1 for r in late
                         if r.event_date == day and not r.collected_time),
        "escalations_this_month": sum(
            1 for r in this_month if r.escalation_stage not in ("none",)),
        "safeguarding_referrals": sum(
            1 for r in late if r.safeguarding_referral),
        "fees_outstanding": round(sum(r.outstanding for r in late), 2),
    }
