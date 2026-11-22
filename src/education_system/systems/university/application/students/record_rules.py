"""Rules for what goes on a student record, shared by every adapter through
``student_lifecycle_service``: contact and entry details, likely
duplicates, and the field-level change history.

Functions that take a connection do not commit; the caller does.
"""

from __future__ import annotations

import re
import unicodedata

from education_system.systems.university.infrastructure.database.schemas import (
    student_records_schema as schema,
)

#: Charging bases. Set by the Finance fee-status assessment
#: (``finance/domain/tuition/fee_status``); "islands" = Channel Islands / Isle of Man.
FEE_STATUSES = ("home", "islands", "international")
MODES = ("full-time", "part-time", "distance", "sandwich")
#: How the student met the entry requirements. Only "a_levels" is checked
#: against a course's UCAS tariff; the others are judged by admissions.
ENTRY_ROUTES = {
    "a_levels": "A levels (UCAS tariff)",
    "btec": "BTEC / vocational",
    "ib": "International Baccalaureate",
    "access": "Access to HE diploma",
    "international": "International qualification",
    "degree": "Degree (postgraduate entry)",
    "mature": "Mature / experience-based",
    "direct_entry": "Direct entry with credit",
}
CONTACT_FIELDS = ("phone", "address", "personal_email", "nationality", "mode_of_study",
                  "fee_status", "preferred_name", "postcode", "notes",
                  "address_line1", "address_line2", "town")
#: The home address as every system's add form asks for it. ``address`` is
#: kept as these joined with commas for the screens and exports that read it.
ADDRESS_LINE_FIELDS = ("address_line1", "address_line2", "town")
#: Who the emergency contact is: the same pick list as the other systems' forms.
EMERGENCY_RELATIONSHIPS = ("Parent", "Carer", "Guardian", "Partner", "Spouse", "Sibling",
                           "Grandparent", "Other relative", "Friend", "Other")
#: Longest staff note or medical note the add form takes.
NOTES_MAX_LENGTH = 2000
_POSTCODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{1,9}$")
_UK_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


def ensure(conn):
    schema.apply_to_connection(conn)


def _check_email(value, errors):
    if value and not _EMAIL.match(value):
        errors["personal_email"] = "is not a valid email address"


def _check_phone(value, errors):
    if value and (not _PHONE.match(value) or sum(c.isdigit() for c in value) < 7):
        errors["phone"] = "must be 7-15 digits, optionally starting with +"


def validate_details(values: dict) -> dict[str, str]:
    """Errors for contact / entry fields present in ``values``."""
    errors: dict[str, str] = {}
    _check_email((values.get("personal_email") or "").strip(), errors)
    _check_phone((values.get("phone") or "").strip(), errors)
    fee = (values.get("fee_status") or "").strip().lower()
    if fee and fee not in FEE_STATUSES:
        errors["fee_status"] = f"must be one of {', '.join(FEE_STATUSES)}"
    mode = (values.get("mode_of_study") or "").strip().lower()
    if mode and mode not in MODES:
        errors["mode_of_study"] = f"must be one of {', '.join(MODES)}"
    for key in ADDRESS_LINE_FIELDS:
        if len((values.get(key) or "").strip()) > 100:
            errors[key] = "must be 100 characters or fewer"
    if len((values.get("preferred_name") or "").strip()) > 40:
        errors["preferred_name"] = "must be 40 characters or fewer"
    postcode = (values.get("postcode") or "").strip()
    if postcode and not _POSTCODE.match(postcode):
        errors["postcode"] = "is not a valid postcode"
    if len((values.get("notes") or "").strip()) > NOTES_MAX_LENGTH:
        errors["notes"] = f"must be {NOTES_MAX_LENGTH} characters or fewer"
    route = (values.get("entry_route") or "").strip()
    if route and route not in ENTRY_ROUTES:
        errors["entry_route"] = "is not a recognised entry route"
    return errors


def normalise_details(values: dict) -> dict:
    out = dict(values)
    for key in ("fee_status", "mode_of_study"):
        if out.get(key):
            out[key] = out[key].strip().lower()
    for key in ("phone", "address", "personal_email", "nationality", "preferred_name", "notes",
                *ADDRESS_LINE_FIELDS):
        if key in out:
            out[key] = (out[key] or "").strip() or None
    if "postcode" in out:
        # UK postcodes get their standard spacing; overseas ones are kept as typed.
        code = " ".join((out["postcode"] or "").upper().split())
        uk = _UK_POSTCODE.match(code)
        out["postcode"] = (f"{uk.group(1)} {uk.group(2)}" if uk else code) or None
    return out


def split_address(text) -> tuple:
    """Line 1, line 2 and town from one address string: one part is line 1,
    two are line 1 and town, more put the middle parts in line 2."""
    parts = [p.strip() for p in re.split(r"[,\n]", str(text or "")) if p.strip()]
    if len(parts) <= 1:
        return (parts[0] if parts else None), None, None
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return parts[0], ", ".join(parts[1:-1]), parts[-1]


def settle_address(values: dict, current: dict | None = None) -> dict:
    """``values`` with ``address`` and its lines agreeing. Lines given (on an
    update: any line key present, the others taken from ``current``) rebuild
    ``address``; a plain ``address`` (API, CSV import) is split into lines."""
    out = dict(values)
    if current is None:
        from_lines = any(values.get(k) for k in ADDRESS_LINE_FIELDS)
    else:
        from_lines = any(k in values for k in ADDRESS_LINE_FIELDS)
    if from_lines:
        lines = [values[k] if k in values else (current or {}).get(k)
                 for k in ADDRESS_LINE_FIELDS]
        out["address"] = ", ".join(str(p).strip() for p in lines if p and str(p).strip()) or None
    elif "address" in values:
        out.update(zip(ADDRESS_LINE_FIELDS, split_address(values.get("address"))))
    return out


def validate_registration(values: dict) -> dict[str, str]:
    """Errors for the add form's emergency contact and medical notes (which
    go to the health record, not onto ``students``)."""
    errors: dict[str, str] = {}
    name = (values.get("emergency_contact_name") or "").strip()
    phone = (values.get("emergency_contact_phone") or "").strip()
    relation = (values.get("emergency_contact_relationship") or "").strip()
    if (name or phone or relation) and not (name and phone):
        errors["emergency_contact"] = "needs both a name and a phone number"
    if phone and (not _PHONE.match(phone) or sum(c.isdigit() for c in phone) < 7):
        errors["emergency_contact_phone"] = "must be 7-15 digits, optionally starting with +"
    if relation and relation.lower() not in {r.lower() for r in EMERGENCY_RELATIONSHIPS}:
        errors["emergency_contact_relationship"] = (
            f"must be one of {', '.join(EMERGENCY_RELATIONSHIPS)}")
    if len((values.get("medical_notes") or "").strip()) > NOTES_MAX_LENGTH:
        errors["medical_notes"] = f"must be {NOTES_MAX_LENGTH} characters or fewer"
    return errors


def relationship_choice(value) -> str:
    """``"parent"`` -> ``"Parent"``; blank stays blank."""
    text = (value or "").strip()
    return next((r for r in EMERGENCY_RELATIONSHIPS if r.lower() == text.lower()), text)


def _fold(text) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def find_duplicates(conn, first_name, last_name, dob, exclude=None) -> list[dict]:
    """Existing students with the same name (ignoring case and accents) and
    date of birth."""
    if not dob:
        return []
    rows = conn.execute("SELECT student_id, first_name, last_name, dob, course, status FROM "
                        "students WHERE dob = ?", (str(dob)[:10],)).fetchall()
    want = (_fold(first_name), _fold(last_name))
    return [{"student_id": r[0], "name": f"{r[1]} {r[2]}", "dob": r[3], "course": r[4],
             "status": r[5]} for r in rows
            if (_fold(r[1]), _fold(r[2])) == want and r[0] != exclude]


def _text(value):
    return None if value is None else str(value)


def record_changes(conn, student_id, old: dict, new: dict, reason, actor_id) -> list[str]:
    """Write one history row per field whose value changed; returns them."""
    ensure(conn)
    changed = [k for k, v in new.items() if _text(v) != _text(old.get(k))]
    for key in changed:
        conn.execute("INSERT INTO student_record_changes (student_id, field, old_value, "
                     "new_value, reason, actor_id) VALUES (?, ?, ?, ?, ?, ?)",
                     (student_id, key, _text(old.get(key)), _text(new[key]), reason, actor_id))
    return changed


def change_history(conn, student_id) -> list[dict]:
    """Field changes and lifecycle (status/study) changes, newest first."""
    ensure(conn)
    rows = [{"when": r[0], "what": r[1], "old": r[2], "new": r[3], "reason": r[4],
             "by": r[5]} for r in conn.execute(
        "SELECT changed_at, field, old_value, new_value, reason, actor_id FROM "
        "student_record_changes WHERE student_id = ?", (student_id,))]
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'student_lifecycle_history'"
                    ).fetchone():
        rows += [{"when": r[0], "what": str(r[1]).replace("_", " "), "old": r[2], "new": r[3],
                  "reason": r[4], "by": r[5]} for r in conn.execute(
            "SELECT COALESCE(created_at, effective_date), action, COALESCE("
            "CASE WHEN new_programme IS NOT NULL THEN old_programme END, "
            "CASE WHEN new_mode IS NOT NULL THEN old_mode END, "
            "CASE WHEN new_campus IS NOT NULL THEN old_campus END, from_status), "
            "COALESCE(new_programme, new_mode, new_campus, to_status), reason, actor_id "
            "FROM student_lifecycle_history WHERE student_id = ?", (student_id,))]
    return sorted(rows, key=lambda r: str(r["when"] or ""), reverse=True)
