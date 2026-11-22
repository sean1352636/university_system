"""Medical: conditions, care plans, allergies, medicines, first aid.

What the school office and first aiders keep, and what every member of staff
needs to know ("who has what, and what to do").

* **Conditions register** - condition, severity, symptoms, triggers, what to
  do, the individual healthcare plan (agreed and review dates), emergency
  medication and where it's kept (e.g. inhaler in the bag, auto-injectors in
  the office), who diagnosed it, status. A severe or life-threatening
  condition needs "what to do"; an IHP needs a review date (default 12 months).
* **Allergies** - allergen, kind, reaction, severity, anaphylaxis and
  auto-injector, the catering note, what to do. The allergy list for a trip,
  a form or the kitchen.
* **Medicines in school** - medicine, form, strength, dose, frequency, the
  parent's written consent (date and who), prescribed / controlled /
  emergency, where it's kept, quantity, expiry and batch. Expired medicine is
  never accepted; expiry is tracked (expired, expiring in 30 days) and the
  family can be e-mailed to replace it.
* **Medicines given** - dose, time, given by, witnessed by (needed for a
  controlled drug), consent checked, refused, emergency use, parent informed.
  A dose can't be given from a medicine that's expired, gone home or has no
  consent on file - except emergency medication in an emergency. The stock
  goes down as it's used.
* **First aid / accident book and emergencies & drills** - in
  :mod:`medical_incidents` (re-exported here).
* **Who.** :data:`MEDICAL_EDITORS` (office / first aid lead) changes
  records; all staff read the care list and allergy list. Changes are in
  ``medical_audit`` and the activity log - ids only, never conditions.
"""

from __future__ import annotations

import csv
import datetime as _dt
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.medical.domain.medical_common import (  # noqa: F401
    PUPIL_COLS,
    NotFound,
    PermissionDenied,
    ValidationError,
    _audit,
    _blank,
    _bool,
    _choice,
    _date,
    _make,
    _need_pupil,
    _number,
    _pupil,
    _require_editor,
    _require_staff,
    _text,
    add_months,
    family_letter,
    history,
    is_editor,
)
from education_system.systems.secondary.modules.medical.domain.medical_incidents import (  # noqa: F401
    EMERGENCY_TYPES,
    EVENT_KINDS,
    EVENT_OUTCOMES,
    EVENT_STATUSES,
    HOSPITAL_OUTCOMES,
    INJURY_TYPES,
    OUTCOMES,
    PERSON_TYPES,
    RIDDOR_DAYS,
    SEVERITIES,
    TOLD_HOW,
    Emergency,
    Incident,
    check_incident,
    close_emergency,
    create_emergency,
    create_incident,
    delete_emergency,
    delete_incident,
    drills_this_term,
    emergency_summary,
    first_aid_summary,
    get_emergency,
    get_incident,
    list_emergencies,
    list_incidents,
    notify_parents,
    record_parents_told,
    record_riddor,
    riddor_outstanding,
    set_emergency_status,
    update_emergency,
    update_incident,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

CONDITIONS: tuple[str, ...] = (
    "Asthma", "Anaphylaxis / severe allergy", "Diabetes (type 1)", "Diabetes (type 2)",
    "Epilepsy", "Sickle cell disease", "Cystic fibrosis", "Heart condition",
    "Migraine", "Eczema", "Coeliac disease", "Crohn's / colitis", "ADHD (medicated)",
    "Mental health", "Hearing impairment", "Visual impairment", "Mobility", "Other")
CONDITION_SEVERITIES: tuple[str, ...] = ("Mild", "Moderate", "Severe", "Life-threatening")
SERIOUS = frozenset({"Severe", "Life-threatening"})
CONDITION_STATUSES: tuple[str, ...] = ("Active", "Resolved")
ALLERGY_KINDS: tuple[str, ...] = ("Food", "Medication", "Insect sting", "Latex",
                                  "Environmental", "Other")
MEDICINE_FORMS: tuple[str, ...] = (
    "Inhaler", "Adrenaline auto-injector", "Tablets", "Capsules", "Liquid", "Insulin pen",
    "Glucose gel", "Buccal midazolam", "Cream / ointment", "Eye / ear drops", "Other")
MEDICINE_STATUSES: tuple[str, ...] = ("In school", "Returned home", "Disposed")
IHP_REVIEW_MONTHS = 12
EXPIRY_WARNING_DAYS = 30
LOW_STOCK = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS medical_conditions (
    condition_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id              INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    condition             TEXT NOT NULL,
    severity              TEXT NOT NULL DEFAULT 'Moderate'
                          CHECK (severity IN ('Mild', 'Moderate', 'Severe', 'Life-threatening')),
    symptoms              TEXT,
    triggers              TEXT,
    what_to_do            TEXT,
    emergency_medication  TEXT,
    medication_location   TEXT,
    has_ihp               INTEGER NOT NULL DEFAULT 0 CHECK (has_ihp IN (0, 1)),
    ihp_agreed_on         TEXT,
    ihp_review_date       TEXT,
    diagnosed_by          TEXT,
    status                TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Resolved')),
    notes                 TEXT,
    created_by            TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by            TEXT,
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_conditions_pupil ON medical_conditions (pupil_id, status);
CREATE TABLE IF NOT EXISTS medical_allergies (
    allergy_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    allergen       TEXT NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'Food',
    reaction       TEXT,
    severity       TEXT NOT NULL DEFAULT 'Moderate'
                   CHECK (severity IN ('Mild', 'Moderate', 'Severe', 'Life-threatening')),
    anaphylaxis    INTEGER NOT NULL DEFAULT 0 CHECK (anaphylaxis IN (0, 1)),
    auto_injector  INTEGER NOT NULL DEFAULT 0 CHECK (auto_injector IN (0, 1)),
    dietary        TEXT,
    action         TEXT,
    status         TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Resolved')),
    notes          TEXT,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by     TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_allergies_pupil ON medical_allergies (pupil_id, status);
CREATE TABLE IF NOT EXISTS medical_medicines (
    medicine_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    form          TEXT NOT NULL DEFAULT 'Tablets',
    strength      TEXT,
    dose          TEXT NOT NULL,
    frequency     TEXT,
    purpose       TEXT,
    emergency     INTEGER NOT NULL DEFAULT 0 CHECK (emergency IN (0, 1)),
    controlled    INTEGER NOT NULL DEFAULT 0 CHECK (controlled IN (0, 1)),
    prescribed    INTEGER NOT NULL DEFAULT 1 CHECK (prescribed IN (0, 1)),
    location      TEXT NOT NULL,
    quantity      INTEGER CHECK (quantity IS NULL OR quantity >= 0),
    expiry_date   TEXT NOT NULL,
    batch         TEXT,
    consent_on    TEXT NOT NULL,
    consent_by    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'In school'
                  CHECK (status IN ('In school', 'Returned home', 'Disposed')),
    notes         TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by    TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_medicines_pupil ON medical_medicines (pupil_id, status);
CREATE TABLE IF NOT EXISTS medical_doses (
    dose_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    medicine_id      INTEGER REFERENCES medical_medicines (medicine_id) ON DELETE SET NULL,
    medicine_name    TEXT NOT NULL,
    dose             TEXT NOT NULL,
    given_at         TEXT NOT NULL,
    given_by         TEXT NOT NULL,
    witnessed_by     TEXT,
    reason           TEXT,
    consent_checked  INTEGER NOT NULL DEFAULT 0 CHECK (consent_checked IN (0, 1)),
    refused          INTEGER NOT NULL DEFAULT 0 CHECK (refused IN (0, 1)),
    emergency        INTEGER NOT NULL DEFAULT 0 CHECK (emergency IN (0, 1)),
    parent_informed  INTEGER NOT NULL DEFAULT 0 CHECK (parent_informed IN (0, 1)),
    notes            TEXT,
    created_by       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_doses_pupil ON medical_doses (pupil_id, given_at);
"""
database.register_schema("medical", _SCHEMA)


@dataclass(frozen=True)
class Condition:
    condition_id: int
    pupil_id: int
    condition: str
    severity: str
    symptoms: str | None
    triggers: str | None
    what_to_do: str | None
    emergency_medication: str | None
    medication_location: str | None
    has_ihp: bool
    ihp_agreed_on: str | None
    ihp_review_date: str | None
    diagnosed_by: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0


@dataclass(frozen=True)
class Allergy:
    allergy_id: int
    pupil_id: int
    allergen: str
    kind: str
    reaction: str | None
    severity: str
    anaphylaxis: bool
    auto_injector: bool
    dietary: str | None
    action: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0


@dataclass(frozen=True)
class Medicine:
    medicine_id: int
    pupil_id: int
    name: str
    form: str
    strength: str | None
    dose: str
    frequency: str | None
    purpose: str | None
    emergency: bool
    controlled: bool
    prescribed: bool
    location: str
    quantity: int | None
    expiry_date: str
    batch: str | None
    consent_on: str
    consent_by: str
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def expired(self) -> bool:
        return self.expiry_date < _today().isoformat()

    @property
    def expiring(self) -> bool:
        soon = (_today() + _dt.timedelta(days=EXPIRY_WARNING_DAYS)).isoformat()
        return not self.expired and self.expiry_date <= soon

    @property
    def label(self) -> str:
        return " ".join(x for x in (self.name, self.strength or "", f"({self.form})") if x)


@dataclass(frozen=True)
class Dose:
    dose_id: int
    pupil_id: int
    medicine_id: int | None
    medicine_name: str
    dose: str
    given_at: str
    given_by: str
    witnessed_by: str | None
    reason: str | None
    consent_checked: bool
    refused: bool
    emergency: bool
    parent_informed: bool
    notes: str | None
    created_by: str | None
    created_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0


_BOOLS = ("has_ihp", "anaphylaxis", "auto_injector", "emergency", "controlled", "prescribed",
          "consent_checked", "refused", "parent_informed")


def _obj(cls, r):
    o = _make(cls, r)
    vals = {k: bool(getattr(o, k)) for k in _BOOLS if k in cls.__dataclass_fields__}
    return cls(**{**{k: getattr(o, k) for k in cls.__dataclass_fields__}, **vals})


def _select(table: str) -> str:
    return f"SELECT x.*, {PUPIL_COLS} FROM {table} x JOIN pupils p USING (pupil_id)"


def _list(cls, table: str, order: str, *, pupil_id=None, year_group=None, form_group=None,
          **eq: Any) -> list:
    where, params = [], []
    if not _blank(pupil_id):
        where.append("x.pupil_id = ?")
        params.append(int(pupil_id))
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if form_group:
        where.append("upper(p.form_group) = upper(?)")
        params.append(form_group)
    for col, val in eq.items():
        if not _blank(val):
            where.append(f"x.{col} = ?")
            params.append(val)
    sql = _select(table) + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {order}"
    with database.connect() as conn:
        return [_obj(cls, r) for r in conn.execute(sql, params)]


def _get(cls, table: str, key: str, value: int, label: str):
    with database.connect() as conn:
        r = conn.execute(_select(table) + f" WHERE x.{key} = ?", (int(value),)).fetchone()
    if r is None:
        raise NotFound(f"No {label} #{value}")
    return _obj(cls, r)


def _write(table: str, key: str, item: str, fields: tuple[str, ...], c: dict[str, Any],
           pupil: P.Pupil, actor: Principal) -> int:
    with database.connect() as conn:
        new_id = conn.execute(
            f"INSERT INTO {table} (pupil_id, {', '.join(fields)}, created_by, updated_by) "
            f"VALUES (?, {', '.join('?' * len(fields))}, ?, ?)",
            (pupil.pupil_id, *(c[k] for k in fields), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, item, "create", pupil_id=pupil.pupil_id, item_id=new_id)
    activity_log.record(f"medical.{item}", target=pupil.admission_no, principal=actor,
                        item=new_id)
    return int(new_id)


def _change(table: str, key: str, item: str, fields: tuple[str, ...], c: dict[str, Any],
            cur: Any, actor: Principal) -> None:
    changed = [k for k in fields if c[k] != (int(getattr(cur, k)) if k in _BOOLS
                                             else getattr(cur, k))]
    if not changed:
        return
    with database.connect() as conn:
        conn.execute(f"UPDATE {table} SET " + ", ".join(f"{k} = ?" for k in changed)
                     + f", updated_by = ?, updated_at = datetime('now') WHERE {key} = ?",
                     (*(c[k] for k in changed), actor.username, getattr(cur, key)))
        _audit(conn, actor, item, "update", pupil_id=cur.pupil_id, item_id=getattr(cur, key),
               fields=changed)
    activity_log.record(f"medical.{item}_update", target=cur.admission_no, principal=actor,
                        item=getattr(cur, key))


def _remove(table: str, key: str, item: str, cur: Any, actor: Principal) -> bool:
    with database.connect() as conn:
        conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (getattr(cur, key),))
        _audit(conn, actor, item, "delete", pupil_id=cur.pupil_id, item_id=getattr(cur, key))
    activity_log.record(f"medical.{item}_delete", target=cur.admission_no, principal=actor,
                        item=getattr(cur, key))
    return True


def _merged(fields: tuple[str, ...], data: dict[str, Any], cur: Any) -> dict[str, Any]:
    m = {k: getattr(cur, k) for k in fields} if cur else {}
    m.update({k: v for k, v in data.items() if k in fields})
    return m


def _pupil_for(data: dict[str, Any], problems: list[str]) -> P.Pupil | None:
    ref = data.get("pupil_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil ID is required" if _blank(ref) else f"No pupil {ref}")
    return p


# ── Conditions ───────────────────────────────────────────────────────

_COND_FIELDS = ("condition", "severity", "symptoms", "triggers", "what_to_do",
                "emergency_medication", "medication_location", "has_ihp", "ihp_agreed_on",
                "ihp_review_date", "diagnosed_by", "status", "notes")


def _clean_condition(data: dict[str, Any], cur: Condition | None, problems: list[str]
                     ) -> dict[str, Any]:
    m = _merged(_COND_FIELDS, data, cur)
    out: dict[str, Any] = {
        "condition": _text(m.get("condition"), 120),
        "severity": _choice(m.get("severity"), CONDITION_SEVERITIES, "Severity", problems,
                            "Moderate"),
        "status": _choice(m.get("status"), CONDITION_STATUSES, "Status", problems, "Active")}
    if not out["condition"]:
        problems.append("Condition is required")
    for k, n in (("symptoms", 1000), ("triggers", 1000), ("what_to_do", 2000),
                 ("emergency_medication", 300), ("medication_location", 200),
                 ("diagnosed_by", 120), ("notes", 2000)):
        out[k] = _text(m.get(k), n)
    out["has_ihp"] = int(_bool(m.get("has_ihp")))
    out["ihp_agreed_on"] = _date(m.get("ihp_agreed_on"), "IHP agreed on", problems)
    out["ihp_review_date"] = _date(m.get("ihp_review_date"), "IHP review date", problems)
    if out["severity"] in SERIOUS and not out["what_to_do"]:
        problems.append("A severe or life-threatening condition needs \"what to do\" - staff "
                        "must know how to respond")
    if out["emergency_medication"] and not out["medication_location"]:
        problems.append("Say where the emergency medication is kept")
    if out["has_ihp"]:
        out["ihp_agreed_on"] = out["ihp_agreed_on"] or _today().isoformat()
        if out["ihp_agreed_on"] > _today().isoformat():
            problems.append("The IHP agreed date can't be in the future")
        if not out["ihp_review_date"] and not any("IHP review" in x for x in problems):
            out["ihp_review_date"] = add_months(out["ihp_agreed_on"],
                                                IHP_REVIEW_MONTHS).isoformat()
        if out["ihp_review_date"] and out["ihp_review_date"] <= out["ihp_agreed_on"]:
            problems.append("The IHP review must be after it was agreed")
    return out


def get_condition(condition_id: int) -> Condition:
    return _get(Condition, "medical_conditions", "condition_id", condition_id, "condition")


def list_conditions(*, pupil_id: int | None = None, year_group: int | str | None = None,
                    form_group: str | None = None, status: str | None = "Active",
                    severity: str | None = None, condition: str | None = None
                    ) -> list[Condition]:
    return _list(Condition, "medical_conditions",
                 "CASE x.severity WHEN 'Life-threatening' THEN 0 WHEN 'Severe' THEN 1 "
                 "WHEN 'Moderate' THEN 2 ELSE 3 END, p.legal_last_name COLLATE NOCASE",
                 pupil_id=pupil_id, year_group=year_group, form_group=form_group,
                 status=status, severity=severity, condition=condition)


def add_condition(data: dict[str, Any], *, actor: Principal) -> Condition:
    _require_editor(actor, "condition")
    problems: list[str] = []
    p = _pupil_for(data, problems)
    c = _clean_condition(data, None, problems)
    if problems:
        raise ValidationError(problems)
    return get_condition(_write("medical_conditions", "condition_id", "condition",
                                _COND_FIELDS, c, p, actor))


def update_condition(condition_id: int, changes: dict[str, Any], *, actor: Principal
                     ) -> Condition:
    cur = get_condition(condition_id)
    _require_editor(actor, "condition_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_condition(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    _change("medical_conditions", "condition_id", "condition", _COND_FIELDS, c, cur, actor)
    return get_condition(cur.condition_id)


def review_ihp(condition_id: int, *, actor: Principal, reviewed_on: str | None = None,
               next_review: str | None = None, note: str = "") -> Condition:
    """The IHP was reviewed with the family: agreed date moves on, next review
    12 months later unless given."""
    cur = get_condition(condition_id)
    on = reviewed_on or _today().isoformat()
    changes: dict[str, Any] = {"has_ihp": True, "ihp_agreed_on": on,
                               "ihp_review_date": next_review or
                               add_months(on, IHP_REVIEW_MONTHS).isoformat()}
    if note.strip():
        changes["notes"] = ((cur.notes + "\n") if cur.notes else "") + \
            f"IHP reviewed {on}: {note.strip()}"
    return update_condition(condition_id, changes, actor=actor)


def delete_condition(condition_id: int, *, actor: Principal) -> bool:
    cur = get_condition(condition_id)
    _require_editor(actor, "condition_delete", cur.admission_no)
    return _remove("medical_conditions", "condition_id", "condition", cur, actor)


# ── Allergies ────────────────────────────────────────────────────────

_ALG_FIELDS = ("allergen", "kind", "reaction", "severity", "anaphylaxis", "auto_injector",
               "dietary", "action", "status", "notes")


def _clean_allergy(data: dict[str, Any], cur: Allergy | None, problems: list[str]
                   ) -> dict[str, Any]:
    m = _merged(_ALG_FIELDS, data, cur)
    out: dict[str, Any] = {
        "allergen": _text(m.get("allergen"), 120),
        "kind": _choice(m.get("kind"), ALLERGY_KINDS, "Kind", problems, "Food"),
        "severity": _choice(m.get("severity"), CONDITION_SEVERITIES, "Severity", problems,
                            "Moderate"),
        "status": _choice(m.get("status"), CONDITION_STATUSES, "Status", problems, "Active"),
        "anaphylaxis": int(_bool(m.get("anaphylaxis"))),
        "auto_injector": int(_bool(m.get("auto_injector")))}
    if not out["allergen"]:
        problems.append("Allergen is required")
    for k, n in (("reaction", 500), ("dietary", 300), ("action", 2000), ("notes", 1000)):
        out[k] = _text(m.get(k), n)
    if out["anaphylaxis"]:
        out["severity"] = "Life-threatening"
    if out["severity"] in SERIOUS and not out["action"]:
        problems.append("A severe allergy needs \"what to do\"")
    if out["kind"] == "Food" and out["status"] == "Active" and not out["dietary"]:
        out["dietary"] = f"No {out['allergen']}"
    return out


def get_allergy(allergy_id: int) -> Allergy:
    return _get(Allergy, "medical_allergies", "allergy_id", allergy_id, "allergy")


def list_allergies(*, pupil_id: int | None = None, year_group: int | str | None = None,
                   form_group: str | None = None, status: str | None = "Active",
                   kind: str | None = None) -> list[Allergy]:
    return _list(Allergy, "medical_allergies",
                 "x.anaphylaxis DESC, p.year_group, p.legal_last_name COLLATE NOCASE",
                 pupil_id=pupil_id, year_group=year_group, form_group=form_group,
                 status=status, kind=kind)


def add_allergy(data: dict[str, Any], *, actor: Principal) -> Allergy:
    _require_editor(actor, "allergy")
    problems: list[str] = []
    p = _pupil_for(data, problems)
    c = _clean_allergy(data, None, problems)
    if problems:
        raise ValidationError(problems)
    return get_allergy(_write("medical_allergies", "allergy_id", "allergy", _ALG_FIELDS, c, p,
                              actor))


def update_allergy(allergy_id: int, changes: dict[str, Any], *, actor: Principal) -> Allergy:
    cur = get_allergy(allergy_id)
    _require_editor(actor, "allergy_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_allergy(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    _change("medical_allergies", "allergy_id", "allergy", _ALG_FIELDS, c, cur, actor)
    return get_allergy(cur.allergy_id)


def delete_allergy(allergy_id: int, *, actor: Principal) -> bool:
    cur = get_allergy(allergy_id)
    _require_editor(actor, "allergy_delete", cur.admission_no)
    return _remove("medical_allergies", "allergy_id", "allergy", cur, actor)


# ── Medicines in school ──────────────────────────────────────────────

_MED_FIELDS = ("name", "form", "strength", "dose", "frequency", "purpose", "emergency",
               "controlled", "prescribed", "location", "quantity", "expiry_date", "batch",
               "consent_on", "consent_by", "status", "notes")


def _clean_medicine(data: dict[str, Any], cur: Medicine | None, problems: list[str]
                    ) -> dict[str, Any]:
    m = _merged(_MED_FIELDS, data, cur)
    out: dict[str, Any] = {
        "form": _choice(m.get("form"), MEDICINE_FORMS, "Form", problems, "Tablets"),
        "status": _choice(m.get("status"), MEDICINE_STATUSES, "Status", problems, "In school"),
        "emergency": int(_bool(m.get("emergency"))),
        "controlled": int(_bool(m.get("controlled"))),
        "prescribed": int(_bool(m.get("prescribed")) if "prescribed" in m else 1)}
    for k, label, n in (("name", "Medicine", 120), ("dose", "Dose", 120),
                        ("location", "Where it's kept", 200),
                        ("consent_by", "Consent given by", 120)):
        out[k] = _text(m.get(k), n)
        if not out[k]:
            problems.append(f"{label} is required")
    for k, n in (("strength", 60), ("frequency", 120), ("purpose", 300), ("batch", 60),
                 ("notes", 1000)):
        out[k] = _text(m.get(k), n)
    q = _number(m.get("quantity"), "Quantity", problems, hi=10000, whole=True)
    out["quantity"] = None if q is None else int(q)
    out["expiry_date"] = _date(m.get("expiry_date"), "Expiry date", problems)
    if not out["expiry_date"] and not any(x.startswith("Expiry") for x in problems):
        problems.append("Expiry date is required")
    out["consent_on"] = _date(m.get("consent_on"), "Consent date", problems)
    if not out["consent_on"] and not any(x.startswith("Consent date") for x in problems):
        problems.append("The parent's written consent is required (date)")
    if out["consent_on"] and out["consent_on"] > _today().isoformat():
        problems.append("The consent date can't be in the future")
    if cur is None and out["expiry_date"] and out["expiry_date"] < _today().isoformat():
        problems.append("This medicine has expired - don't accept it; ask the family for an "
                        "in-date supply")
    if out["controlled"] and out["location"] and "lock" not in out["location"].lower():
        problems.append("A controlled drug must be kept locked away - say which locked "
                        "cupboard")
    return out


def get_medicine(medicine_id: int) -> Medicine:
    return _get(Medicine, "medical_medicines", "medicine_id", medicine_id, "medicine")


def list_medicines(*, pupil_id: int | None = None, year_group: int | str | None = None,
                   form_group: str | None = None, status: str | None = "In school",
                   emergency: bool | None = None) -> list[Medicine]:
    rows = _list(Medicine, "medical_medicines", "x.expiry_date, p.legal_last_name",
                 pupil_id=pupil_id, year_group=year_group, form_group=form_group,
                 status=status)
    return [m for m in rows if emergency is None or m.emergency == emergency]


def add_medicine(data: dict[str, Any], *, actor: Principal) -> Medicine:
    _require_editor(actor, "medicine")
    problems: list[str] = []
    p = _pupil_for(data, problems)
    c = _clean_medicine(data, None, problems)
    if problems:
        raise ValidationError(problems)
    return get_medicine(_write("medical_medicines", "medicine_id", "medicine", _MED_FIELDS, c,
                               p, actor))


def update_medicine(medicine_id: int, changes: dict[str, Any], *, actor: Principal
                    ) -> Medicine:
    cur = get_medicine(medicine_id)
    _require_editor(actor, "medicine_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_medicine(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    _change("medical_medicines", "medicine_id", "medicine", _MED_FIELDS, c, cur, actor)
    return get_medicine(cur.medicine_id)


def return_medicine(medicine_id: int, *, actor: Principal, disposed: bool = False,
                    note: str = "") -> Medicine:
    """The medicine went home (or was disposed of, e.g. expired)."""
    cur = get_medicine(medicine_id)
    changes: dict[str, Any] = {"status": "Disposed" if disposed else "Returned home"}
    if note.strip():
        changes["notes"] = ((cur.notes + "\n") if cur.notes else "") + note.strip()
    return update_medicine(medicine_id, changes, actor=actor)


def delete_medicine(medicine_id: int, *, actor: Principal) -> bool:
    cur = get_medicine(medicine_id)
    _require_editor(actor, "medicine_delete", cur.admission_no)
    with database.connect() as conn:
        used = conn.execute("SELECT COUNT(*) FROM medical_doses WHERE medicine_id = ?",
                            (cur.medicine_id,)).fetchone()[0]
    if used:
        raise ValidationError(["Doses have been given from this medicine - mark it returned "
                               "or disposed instead (the log is kept)"])
    return _remove("medical_medicines", "medicine_id", "medicine", cur, actor)


def expiring(*, within: int = EXPIRY_WARNING_DAYS, today: _dt.date | None = None
             ) -> list[Medicine]:
    """Medicines in school that have expired or expire within *within* days."""
    horizon = ((today or _today()) + _dt.timedelta(days=within)).isoformat()
    return [m for m in list_medicines() if m.expiry_date <= horizon]


def ask_for_replacement(medicine_id: int, *, actor: Principal, note: str = ""
                        ) -> dict[str, Any]:
    """E-mail the family that a medicine has expired / is expiring."""
    m = get_medicine(medicine_id)
    _require_editor(actor, "medicine_notify", m.admission_no)
    p = P.get_pupil(m.pupil_id)
    res = family_letter("medical_medicine_expiry", "Medicine expiry", p, {
        "medicine": m.label, "expiry_date": m.expiry_date,
        "state": "has expired" if m.expired else "expires soon", "note": note.strip()}, actor)
    with database.connect() as conn:
        _audit(conn, actor, "medicine", "notify", pupil_id=m.pupil_id, item_id=m.medicine_id,
               emails=res["emails"])
    activity_log.record("medical.medicine_notify", target=m.admission_no, principal=actor,
                        emails=res["emails"])
    return res


# ── Medicines given ──────────────────────────────────────────────────

def list_doses(*, pupil_id: int | None = None, medicine_id: int | None = None,
               from_date: str | None = None, to_date: str | None = None,
               year_group: int | str | None = None, limit: int = 2000) -> list[Dose]:
    rows = _list(Dose, "medical_doses", "x.given_at DESC, x.dose_id DESC",
                 pupil_id=pupil_id, year_group=year_group, medicine_id=medicine_id)
    rows = [d for d in rows if (not from_date or d.given_at[:10] >= from_date) and
            (not to_date or d.given_at[:10] <= to_date)]
    return rows[:limit]


def get_dose(dose_id: int) -> Dose:
    return _get(Dose, "medical_doses", "dose_id", dose_id, "dose")


def give_dose(data: dict[str, Any], *, actor: Principal) -> Dose:
    """Record a medicine given (or refused). *data*: ``medicine_id`` (a
    medicine in school) or ``pupil_id`` + ``medicine_name``; ``dose``,
    ``given_at`` (blank = now), ``given_by``, ``witnessed_by``,
    ``consent_checked``, ``refused``, ``emergency``, ``units`` (taken off the
    stock, default 1), ``parent_informed``, ``reason``, ``notes``."""
    _require_editor(actor, "dose")
    problems: list[str] = []
    med: Medicine | None = None
    if not _blank(data.get("medicine_id")):
        try:
            med = get_medicine(int(data["medicine_id"]))
        except (ValueError, NotFound):
            problems.append(f"No medicine #{data.get('medicine_id')}")
    p = P.get_pupil(med.pupil_id) if med else _pupil_for(data, problems)
    emergency = _bool(data.get("emergency"))
    refused = _bool(data.get("refused"))
    consent = _bool(data.get("consent_checked"))
    name = _text(data.get("medicine_name"), 120) or (med.name if med else None)
    dose = _text(data.get("dose"), 120) or (med.dose if med else None)
    if not name:
        problems.append("Medicine is required")
    if not dose:
        problems.append("Dose is required")
    raw = str(data.get("given_at") or "").strip()
    try:
        at = _dt.datetime.fromisoformat(raw) if raw else _dt.datetime.now()
    except ValueError:
        problems.append("Given at must be a date and time (YYYY-MM-DD HH:MM)")
        at = _dt.datetime.now()
    if at > _dt.datetime.now() + _dt.timedelta(minutes=5):
        problems.append("A dose can't be recorded before it's given")
    given_by = _text(data.get("given_by"), 80)
    if not given_by:
        problems.append("Given by is required")
    witness = _text(data.get("witnessed_by"), 80)
    if med is not None:
        if med.status != "In school" and not emergency:
            problems.append(f"{med.label} is not in school ({med.status.lower()})")
        if med.expiry_date < at.date().isoformat() and not emergency:
            problems.append(f"{med.label} expired on {med.expiry_date} - don't give it")
        if not consent and not emergency:
            problems.append("Check the parent's consent and the label (pupil, medicine, dose, "
                            "time) before giving it")
        if med.controlled and not refused and not witness:
            problems.append("A controlled drug needs a second member of staff to witness it")
        if emergency and not med.emergency and not consent:
            problems.append("Only emergency medication can be given without the consent check")
    elif not consent and not emergency:
        problems.append("Medicine not held in school: check written consent first")
    units = _number(data.get("units"), "Units", problems, hi=100, whole=True)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        did = conn.execute(
            "INSERT INTO medical_doses (pupil_id, medicine_id, medicine_name, dose, given_at, "
            "given_by, witnessed_by, reason, consent_checked, refused, emergency, "
            "parent_informed, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p.pupil_id, med.medicine_id if med else None, name, dose,
             at.isoformat(sep=" ", timespec="minutes"), given_by, witness,
             _text(data.get("reason"), 300), int(consent), int(refused), int(emergency),
             int(_bool(data.get("parent_informed"))), _text(data.get("notes"), 1000),
             actor.username)).lastrowid
        if med is not None and med.quantity is not None and not refused:
            conn.execute("UPDATE medical_medicines SET quantity = MAX(0, quantity - ?) "
                         "WHERE medicine_id = ?", (int(units if units is not None else 1),
                                                   med.medicine_id))
        _audit(conn, actor, "dose", "give", pupil_id=p.pupil_id, item_id=did,
               medicine=med.medicine_id if med else None, refused=refused, emergency=emergency)
    activity_log.record("medical.dose", target=p.admission_no, principal=actor, dose=did)
    return get_dose(did)


def delete_dose(dose_id: int, *, actor: Principal, reason: str) -> bool:
    """Remove a dose recorded in error (needs a reason; the stock is put back)."""
    d = get_dose(dose_id)
    _require_editor(actor, "dose_delete", d.admission_no)
    if not reason.strip():
        raise ValidationError(["Say why the entry is removed"])
    with database.connect() as conn:
        conn.execute("DELETE FROM medical_doses WHERE dose_id = ?", (d.dose_id,))
        if d.medicine_id and not d.refused:
            conn.execute("UPDATE medical_medicines SET quantity = quantity + 1 "
                         "WHERE medicine_id = ? AND quantity IS NOT NULL", (d.medicine_id,))
        _audit(conn, actor, "dose", "delete", pupil_id=d.pupil_id, item_id=d.dose_id,
               reason=reason.strip()[:200])
    activity_log.record("medical.dose_delete", target=d.admission_no, principal=actor)
    return True


def doses_today(pupil_id: int, medicine_id: int | None = None,
                day: _dt.date | None = None) -> list[Dose]:
    iso = (day or _today()).isoformat()
    return [d for d in list_doses(pupil_id=pupil_id, medicine_id=medicine_id,
                                  from_date=iso, to_date=iso) if not d.refused]


# ── What staff need ──────────────────────────────────────────────────

def care_list(*, actor: Principal, year_group: int | str | None = None,
              form_group: str | None = None, pupil_ids: list[int] | None = None,
              serious_only: bool = False) -> list[dict[str, Any]]:
    """Who has what and what to do: one row per pupil with an active
    condition or allergy - conditions (severity), what to do, emergency
    medication and where it is, allergies, IHP. Most serious first."""
    _require_staff(actor, "care_list")
    conds = list_conditions(year_group=year_group, form_group=form_group)
    algs = list_allergies(year_group=year_group, form_group=form_group)
    meds = list_medicines(year_group=year_group, form_group=form_group, emergency=True)
    rank = {s: i for i, s in enumerate(reversed(CONDITION_SEVERITIES))}
    out: dict[int, dict[str, Any]] = {}

    def row(x) -> dict[str, Any]:
        return out.setdefault(x.pupil_id, {
            "pupil_id": x.pupil_id, "pupil_name": x.pupil_name, "admission_no": x.admission_no,
            "year_group": x.pupil_year, "conditions": [], "what_to_do": [], "medication": [],
            "allergies": [], "ihp": False, "worst": "Mild", "anaphylaxis": False})
    for c in conds:
        r = row(c)
        r["conditions"].append(f"{c.condition} ({c.severity.lower()})")
        if c.what_to_do:
            r["what_to_do"].append(f"{c.condition}: {c.what_to_do}")
        if c.emergency_medication:
            r["medication"].append(f"{c.emergency_medication} - {c.medication_location}")
        r["ihp"] = r["ihp"] or c.has_ihp
        if rank[c.severity] < rank[r["worst"]]:
            r["worst"] = c.severity
    for a in algs:
        r = row(a)
        r["allergies"].append(a.allergen + (" (ANAPHYLAXIS)" if a.anaphylaxis else ""))
        if a.action:
            r["what_to_do"].append(f"{a.allergen} allergy: {a.action}")
        r["anaphylaxis"] = r["anaphylaxis"] or a.anaphylaxis
        if rank[a.severity] < rank[r["worst"]]:
            r["worst"] = a.severity
    for m in meds:
        if m.pupil_id in out:
            text = f"{m.label} - {m.location}"
            if not any(m.name.lower() in x.lower() for x in out[m.pupil_id]["medication"]):
                out[m.pupil_id]["medication"].append(text)
    rows = list(out.values())
    if pupil_ids is not None:
        keep = {int(i) for i in pupil_ids}
        rows = [r for r in rows if r["pupil_id"] in keep]
    if serious_only:
        rows = [r for r in rows if r["worst"] in SERIOUS]
    activity_log.record("medical.care_list", principal=actor, rows=len(rows))
    return sorted(rows, key=lambda r: (rank[r["worst"]], r["year_group"], r["pupil_name"]))


def allergy_list(*, actor: Principal, year_group: int | str | None = None,
                 form_group: str | None = None, pupil_ids: list[int] | None = None
                 ) -> list[dict[str, Any]]:
    """For a trip or the kitchen: every active allergy with the catering
    note, anaphylaxis, auto-injector and what to do. *pupil_ids* restricts it
    to a trip's pupils."""
    _require_staff(actor, "allergy_list")
    keep = {int(i) for i in pupil_ids} if pupil_ids is not None else None
    rows = [{"pupil_id": a.pupil_id, "pupil_name": a.pupil_name, "admission_no": a.admission_no,
             "year_group": a.pupil_year, "allergen": a.allergen, "kind": a.kind,
             "severity": a.severity, "anaphylaxis": a.anaphylaxis,
             "auto_injector": a.auto_injector, "dietary": a.dietary or "",
             "action": a.action or ""}
            for a in list_allergies(year_group=year_group, form_group=form_group)
            if keep is None or a.pupil_id in keep]
    activity_log.record("medical.allergy_list", principal=actor, rows=len(rows))
    return rows


def for_pupil(pupil_id: int) -> dict[str, Any]:
    """A pupil's medical picture (profile / My Day): conditions, allergies,
    medicines in school, recent first aid."""
    return {"conditions": list_conditions(pupil_id=pupil_id),
            "allergies": list_allergies(pupil_id=pupil_id),
            "medicines": list_medicines(pupil_id=pupil_id),
            "first_aid": list_incidents(pupil_id=pupil_id, limit=10)}


def due(*, within: int = EXPIRY_WARNING_DAYS, today: _dt.date | None = None
        ) -> list[dict[str, Any]]:
    """What needs doing: IHP reviews, medicines expiring or expired, low stock,
    RIDDOR reports, emergencies with actions outstanding. Soonest first."""
    day = today or _today()
    horizon = (day + _dt.timedelta(days=within)).isoformat()
    iso = day.isoformat()
    out: list[dict[str, Any]] = []

    def add(item: str, when: str | None, who: str, pupil_id: int | None, ref: str) -> None:
        out.append({"item": item, "due": when or iso, "overdue": bool(when and when < iso),
                    "who": who, "pupil_id": pupil_id, "ref": ref})
    for c in list_conditions():
        if c.has_ihp and c.ihp_review_date and c.ihp_review_date <= horizon:
            add(f"IHP review: {c.condition}", c.ihp_review_date, c.pupil_name, c.pupil_id,
                f"condition:{c.condition_id}")
        elif c.severity in SERIOUS and not c.has_ihp:
            add(f"No IHP for a {c.severity.lower()} condition: {c.condition}", None,
                c.pupil_name, c.pupil_id, f"condition:{c.condition_id}")
    for m in list_medicines():
        if m.expiry_date <= horizon:
            add(f"Medicine {'expired' if m.expired else 'expiring'}: {m.label}",
                m.expiry_date, m.pupil_name, m.pupil_id, f"medicine:{m.medicine_id}")
        if m.quantity is not None and m.quantity <= LOW_STOCK:
            add(f"Low stock ({m.quantity} left): {m.label}", None, m.pupil_name, m.pupil_id,
                f"medicine:{m.medicine_id}")
    for i in riddor_outstanding():
        add("RIDDOR report to the HSE", i.riddor_due, i.who.split(" (")[0], i.pupil_id,
            f"incident:{i.incident_id}")
    for e in list_emergencies(outstanding_only=True):
        add(f"{e.kind} follow-up: {e.event_type} ({e.status})", None, "-", None,
            f"emergency:{e.event_id}")
    d = drills_this_term(day)
    if not d["this_term"]:
        add("No fire drill this term" + (f" (last {d['last']})" if d["last"] else ""), None,
            "-", None, "")
    return sorted(out, key=lambda x: (not x["overdue"], x["due"], x["item"]))


def summary() -> dict[str, Any]:
    conds = list_conditions()
    return {"conditions": len(conds),
            "by_condition": dict(Counter(c.condition for c in conds).most_common()),
            "by_severity": dict(Counter(c.severity for c in conds)),
            "pupils_with_conditions": len({c.pupil_id for c in conds}),
            "ihps": sum(1 for c in conds if c.has_ihp),
            "allergies": len(list_allergies()),
            "anaphylaxis": sum(1 for a in list_allergies() if a.anaphylaxis),
            "medicines": len(list_medicines()), "expiring": len(expiring()),
            "doses_today": len(list_doses(from_date=_today().isoformat()))}


def dose_report(*, from_date: str | None = None, to_date: str | None = None
                ) -> list[dict[str, Any]]:
    """Doses given by medicine: {'medicine', 'doses', 'refused', 'emergency', 'pupils'}."""
    out: dict[str, dict[str, Any]] = {}
    for d in list_doses(from_date=from_date, to_date=to_date):
        g = out.setdefault(d.medicine_name, {"medicine": d.medicine_name, "doses": 0,
                                             "refused": 0, "emergency": 0, "pupils": set()})
        g["doses" if not d.refused else "refused"] += 1
        g["emergency"] += d.emergency
        g["pupils"].add(d.pupil_id)
    return sorted(({**g, "pupils": len(g["pupils"])} for g in out.values()),
                  key=lambda g: -g["doses"])


# ── Export ───────────────────────────────────────────────────────────

def export_care_list(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    rows = care_list(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year", "most_serious", "conditions",
                    "allergies", "what_to_do", "emergency_medication_and_location", "ihp"])
        for r in rows:
            w.writerow([_safe(r["admission_no"]), _safe(r["pupil_name"]), r["year_group"],
                        r["worst"], _safe("; ".join(r["conditions"])),
                        _safe("; ".join(r["allergies"])), _safe(" | ".join(r["what_to_do"])),
                        _safe("; ".join(r["medication"])), "yes" if r["ihp"] else ""])
    activity_log.record("medical.export", principal=actor, rows=len(rows), kind="care")
    return len(rows)


def export_allergy_list(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    rows = allergy_list(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year", "allergen", "kind", "severity",
                    "anaphylaxis", "auto_injector", "catering", "what_to_do"])
        for r in rows:
            w.writerow([_safe(r["admission_no"]), _safe(r["pupil_name"]), r["year_group"],
                        _safe(r["allergen"]), r["kind"], r["severity"],
                        "yes" if r["anaphylaxis"] else "", "yes" if r["auto_injector"] else "",
                        _safe(r["dietary"]), _safe(r["action"])])
    activity_log.record("medical.export", principal=actor, rows=len(rows), kind="allergy")
    return len(rows)


def export_first_aid(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_incidents(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "date", "time", "person", "type", "year", "location", "injury",
                    "severity", "body_part", "treatment", "treated_by", "outcome",
                    "parents_told", "hospital", "riddor", "riddor_reported", "book_ref"])
        for i in rows:
            w.writerow([i.incident_id, i.incident_date, i.incident_time or "", _safe(i.who),
                        i.person_type, i.pupil_year or "", _safe(i.location), i.injury_type,
                        i.severity, _safe(i.body_part), _safe(i.treatment),
                        _safe(i.treated_by), i.outcome, "yes" if i.parent_contacted else "",
                        "yes" if i.hospital_referral else "",
                        "yes" if i.riddor_reportable else "", i.riddor_reported_on or "",
                        _safe(i.accident_book_ref)])
    activity_log.record("medical.export", principal=actor, rows=len(rows), kind="first_aid")
    return len(rows)
