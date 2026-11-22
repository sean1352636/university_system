"""The schools register: every school and setting the authority admits to,
places children in or funds.

Rules:

* the URN is six digits and unique; the admission number (PAN) is at most
  the school's capacity;
* the number on roll can't be negative; surplus places are worked out;
* a closed school keeps its record (for history) but takes no new
  preferences, offers or placements;
* a school can be marked as this platform's Primary or Secondary School
  (one each): its notifications arrive linked to it, and a place accepted
  or allocated there is handed to it (``platform.cross_system.
  local_authority_links``). Its URN can wait until it is known.
"""

from __future__ import annotations

import re

from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.local_authority.infrastructure import database as db

PHASES = ("Nursery", "Primary", "Middle", "Secondary", "All-through", "Special", "Alternative provision", "Post-16")
TYPES = ("Community", "Voluntary aided", "Voluntary controlled", "Foundation", "Academy",
         "Free school", "Independent", "Independent special", "Pupil referral unit")
OFSTED = ("Outstanding", "Good", "Requires improvement", "Inadequate", "Not yet inspected")
STATUSES = ("Open", "Proposed to close", "Closed")
#: Types the authority is the admission authority for (the rest set their own).
LA_ADMITS = frozenset({"Community", "Voluntary controlled"})
#: "On this platform" choices -> the platform's system key.
PLATFORM_SCHOOLS = {"Primary School (this platform)": "primary",
                    "Secondary School (this platform)": "secondary"}
PLATFORM_PHASES = {"primary": "Primary", "secondary": "Secondary"}
_URN = re.compile(r"^\d{6}$")


def _check_school(values: dict, old: dict | None) -> None:
    from education_system.systems.local_authority.modules import children
    merged = {**(old or {}), **values}
    if values.get("urn"):
        values["urn"] = values["urn"].strip()
        if not _URN.match(values["urn"]):
            raise ValidationError("A URN is six digits.")
    link = merged.get("platform_school") or None
    if not merged.get("urn") and not link:
        raise ValidationError("URN is required.")
    own_id = (old or {}).get("id")
    with db.connect() as conn:
        if values.get("urn") and conn.execute(
                "SELECT 1 FROM schools WHERE urn = ? AND id IS NOT ?",
                (values["urn"], own_id)).fetchone():
            raise ValidationError(f"Another school already has URN {values['urn']}.")
        if link and "platform_school" in values and conn.execute(
                "SELECT 1 FROM schools WHERE platform_school = ? AND id IS NOT ?",
                (link, own_id)).fetchone():
            raise ValidationError(f"Another school is already marked as the {link}.")
    children.check_postcode(values)
    children.check_email(values)
    children.check_phone(values)
    pan, cap = merged.get("pan"), merged.get("capacity")
    if pan is not None and int(pan) < 0 or cap is not None and int(cap) < 0:
        raise ValidationError("Numbers of places can't be negative.")
    if pan is not None and cap is not None and int(pan) > int(cap):
        raise ValidationError("The admission number can't be more than the capacity.")
    if merged.get("on_roll") is not None and int(merged["on_roll"]) < 0:
        raise ValidationError("The number on roll can't be negative.")
    values["la_admits"] = 1 if merged.get("school_type") in LA_ADMITS else 0


def surplus(row: dict) -> str:
    cap, roll = row.get("capacity"), row.get("on_roll")
    if not cap or roll is None:
        return ""
    spare = int(cap) - int(roll)
    return f"{spare} ({round(100 * spare / int(cap))}%)"


SCHOOLS = RecordType(
    key="schools", title="Schools Register", singular="school", order_by="name",
    check=_check_school, filters=("phase", "school_type", "status"),
    describe=lambda row: row.get("name") or "school",
    computed=(("Surplus places", surplus),),
    fields=(
        Field("name", "Name", required=True),
        Field("urn", "URN", help="Required, unless the school is on this platform"),
        Field("phase", "Phase", "choice", PHASES, required=True),
        Field("school_type", "Type", "choice", TYPES, required=True, default="Academy"),
        Field("la_admits", "LA is admission authority", "bool", form=False, listed=False),
        Field("age_range", "Age range", listed=False, help="e.g. 4-11"),
        Field("pan", "Admission number (PAN)", "int"),
        Field("capacity", "Capacity", "int"),
        Field("on_roll", "On roll", "int"),
        Field("ofsted", "Ofsted", "choice", OFSTED, default="Not yet inspected", listed=False),
        Field("headteacher", "Headteacher", listed=False),
        Field("phone", "Phone", listed=False),
        Field("email", "E-mail", listed=False),
        Field("address_line1", "Address", listed=False),
        Field("postcode", "Postcode", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Open"),
        Field("platform_school", "On this platform", "choice", tuple(PLATFORM_SCHOOLS),
              listed=False, help="Linked: notifications arrive from it, places go to it"),
    ),
)


def open_schools() -> list[dict]:
    return [s for s in r.list_records(SCHOOLS) if s["status"] != "Closed"]


def platform_system(school_id: int | None) -> str | None:
    """The platform system key ("primary" / "secondary") of a linked school."""
    row = r.get(SCHOOLS, int(school_id)) if school_id else None
    return PLATFORM_SCHOOLS.get((row or {}).get("platform_school") or "")


def linked_school(system: str, name: str | None = None) -> int:
    """The school marked as this platform's *system*; added (open, URN to
    follow) the first time that school sends a notification."""
    label = next(k for k, v in PLATFORM_SCHOOLS.items() if v == system)
    rows = r.list_records(SCHOOLS, equals={"platform_school": label})
    if rows:
        return rows[0]["id"]
    phase = PLATFORM_PHASES[system]
    return r.save(SCHOOLS, {"name": name or f"{phase} School", "phase": phase,
                            "school_type": "Academy", "platform_school": label,
                            "status": "Open"}, actor="platform")


def school_name(school_id: int | None) -> str:
    row = r.get(SCHOOLS, school_id) if school_id else None
    return row["name"] if row else ""
