"""Learner aims on a census return (the old Census / ILR "Aims" tab).

Kept from the old screen: every field of an aim (learner ref and name,
UKPRN, ULN, aim type, aim reference and title, funding model, start /
planned end / actual end dates, completion and outcome codes, status,
planned and actual hours, funding band value, delivery location, partner
UKPRN, notes), the old lists (all, active, for a return, for a learner),
new / edit / delete, and the aim counts on the Summary.

New:

* **Linked to the pupil.** A learner ref that is an admission number, UPN
  or a pupil's name links the aim to that pupil (``pupil_id``) and fills in
  the name; anything else is kept as typed, as before.
* **Linked to the return.** ``return_id`` points at a census return
  (``census_runs``); deleting the return keeps its aims (unlinked).
* **Rules.** All problems are reported at once; dates must be real dates
  and not end before the start; a completion code must be one of the ILR
  codes; hours and the funding band value can't be negative.
* **Who.** Data managers only (as the rest of the census); the activity log
  records ids only.
"""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.reporting.domain import census as CE  # FK target
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
NotFound = P.NotFound

AIM_TYPES: tuple[str, ...] = ("Programme Aim", "Component Aim", "Core Aim", "Maths", "English",
                              "Tutorial", "Work Placement", "Enrichment", "Other")
DEFAULT_AIM_TYPE = "Programme Aim"
FUNDING_MODELS: tuple[str, ...] = ("16-19 (excluding Apprenticeships)", "Apprenticeship",
                                   "Adult Skills", "Advanced Learner Loans",
                                   "Community Learning", "ESFA Other", "Other")
DEFAULT_FUNDING_MODEL = FUNDING_MODELS[0]
STATUSES: tuple[str, ...] = ("Continuing", "Completed", "Withdrawn", "Transferred", "Achieved",
                             "Partially Achieved", "Not Achieved", "Temporarily Withdrawn")
DEFAULT_STATUS = "Continuing"
ACTIVE_STATUSES = frozenset({"Continuing", "Temporarily Withdrawn"})
#: 1 Continuing, 2 Completed (achieved), 3 Withdrawn, 6 Temporarily withdrawn,
#: 7 Transferred, 10 Completed (not achieved).
COMPLETION_CODES: tuple[int, ...] = (1, 2, 3, 6, 7, 10)

FIELDS: tuple[str, ...] = (
    "return_id", "learner_ref", "learner_name", "ukprn", "uln", "aim_type", "aim_reference",
    "aim_title", "funding_model", "start_date", "planned_end_date", "actual_end_date",
    "completion_code", "outcome_code", "status", "planned_hours", "actual_hours",
    "funding_band_value", "delivery_location", "partner_ukprn", "notes")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS census_aims (
    aim_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id          INTEGER REFERENCES census_runs (return_id) ON DELETE SET NULL,
    pupil_id           INTEGER REFERENCES pupils (pupil_id) ON DELETE SET NULL,
    learner_ref        TEXT NOT NULL,
    learner_name       TEXT,
    ukprn              TEXT,
    uln                TEXT,
    aim_type           TEXT NOT NULL,
    aim_reference      TEXT NOT NULL,
    aim_title          TEXT,
    funding_model      TEXT NOT NULL,
    start_date         TEXT NOT NULL,
    planned_end_date   TEXT,
    actual_end_date    TEXT,
    completion_code    INTEGER,
    outcome_code       TEXT,
    status             TEXT NOT NULL DEFAULT 'Continuing',
    planned_hours      INTEGER,
    actual_hours       INTEGER,
    funding_band_value REAL,
    delivery_location  TEXT,
    partner_ukprn      TEXT,
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT
);
CREATE INDEX IF NOT EXISTS ix_census_aims_learner ON census_aims (learner_ref);
CREATE INDEX IF NOT EXISTS ix_census_aims_return ON census_aims (return_id);
CREATE INDEX IF NOT EXISTS ix_census_aims_status ON census_aims (status);
CREATE INDEX IF NOT EXISTS ix_census_aims_pupil ON census_aims (pupil_id);
"""
database.register_schema("census_aims", _SCHEMA)


@dataclass(frozen=True)
class Aim:
    aim_id: int
    return_id: int | None
    pupil_id: int | None
    learner_ref: str
    learner_name: str | None
    ukprn: str | None
    uln: str | None
    aim_type: str
    aim_reference: str
    aim_title: str | None
    funding_model: str
    start_date: str
    planned_end_date: str | None
    actual_end_date: str | None
    completion_code: int | None
    outcome_code: str | None
    status: str
    planned_hours: int | None
    actual_hours: int | None
    funding_band_value: float | None
    delivery_location: str | None
    partner_ukprn: str | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES


def _row(r) -> Aim:
    return Aim(**{k: r[k] for k in Aim.__dataclass_fields__})


# ── Cleaning ─────────────────────────────────────────────────────────

def _text(v: Any, limit: int = 200) -> str | None:
    return (str(v).strip()[:limit] or None) if v not in (None, "") else None


def _date(v: Any, label: str, problems: list[str]) -> str | None:
    t = _text(v, 10)
    if t is None:
        return None
    try:
        return _dt.date.fromisoformat(t).isoformat()
    except ValueError:
        problems.append(f"{label}: '{t}' isn't a date (YYYY-MM-DD)")
        return None


def _number(v: Any, label: str, problems: list[str], kind=int) -> Any:
    if v in (None, ""):
        return None
    try:
        n = kind(str(v).strip())
    except ValueError:
        problems.append(f"{label} must be a {'whole ' if kind is int else ''}number")
        return None
    if n < 0:
        problems.append(f"{label} can't be negative")
        return None
    return n


def _choice(v: Any, options: tuple[str, ...], default: str, label: str,
            problems: list[str]) -> str:
    t = _text(v) or default
    match = next((o for o in options if o.lower() == t.lower()), None)
    if match is None:
        problems.append(f"{label} must be one of: {', '.join(options)}")
        return default
    return match


def _clean(data: dict[str, Any], current: Aim | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}

    ref = _text(merged.get("learner_ref"), 60)
    out["pupil_id"] = None
    if not ref:
        problems.append("Learner ref is required")
    else:
        pupil = P.find_by_reference(ref)
        if pupil is not None:
            out["pupil_id"] = pupil.pupil_id
            ref = pupil.admission_no
            merged["learner_name"] = merged.get("learner_name") or pupil.display_name
    out["learner_ref"] = ref
    out["aim_type"] = _choice(merged.get("aim_type"), AIM_TYPES, DEFAULT_AIM_TYPE, "Aim type",
                              problems)
    out["funding_model"] = _choice(merged.get("funding_model"), FUNDING_MODELS,
                                   DEFAULT_FUNDING_MODEL, "Funding model", problems)
    out["status"] = _choice(merged.get("status"), STATUSES, DEFAULT_STATUS, "Status", problems)
    out["aim_reference"] = _text(merged.get("aim_reference"), 30)
    if not out["aim_reference"]:
        problems.append("Aim reference is required")
    out["start_date"] = _date(merged.get("start_date"), "Start date", problems)
    if not merged.get("start_date"):
        problems.append("Start date is required")
    for key, label in (("planned_end_date", "Planned end date"),
                       ("actual_end_date", "Actual end date")):
        out[key] = _date(merged.get(key), label, problems)
        if out[key] and out["start_date"] and out[key] < out["start_date"]:
            problems.append(f"{label} can't be before the start date")
    cc = _number(merged.get("completion_code"), "Completion code", problems)
    if cc is not None and cc not in COMPLETION_CODES:
        problems.append("Completion code must be one of "
                        + ", ".join(str(c) for c in COMPLETION_CODES))
    out["completion_code"] = cc
    rid = _number(merged.get("return_id"), "Return id", problems)
    if rid:
        with database.connect() as conn:
            if conn.execute("SELECT 1 FROM census_runs WHERE return_id = ?",
                            (rid,)).fetchone() is None:
                problems.append(f"No census return #{rid}")
    out["return_id"] = rid or None
    out["planned_hours"] = _number(merged.get("planned_hours"), "Planned hours", problems)
    out["actual_hours"] = _number(merged.get("actual_hours"), "Actual hours", problems)
    out["funding_band_value"] = _number(merged.get("funding_band_value"),
                                        "Funding band value", problems, float)
    for key, limit in (("learner_name", 120), ("ukprn", 8), ("uln", 10), ("aim_title", 200),
                       ("outcome_code", 10), ("delivery_location", 120),
                       ("partner_ukprn", 8), ("notes", 2000)):
        out[key] = _text(merged.get(key), limit)
    if problems:
        raise ValidationError(problems)
    return out


# ── CRUD ─────────────────────────────────────────────────────────────

def get_aim(aim_id: int, *, actor: Principal) -> Aim:
    RC.require_data_manager(actor, "census.aims", "census returns")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM census_aims WHERE aim_id = ?", (int(aim_id),)).fetchone()
    if r is None:
        raise NotFound(f"No aim #{aim_id}")
    return _row(r)


def create_aim(data: dict[str, Any], *, actor: Principal) -> Aim:
    RC.require_data_manager(actor, "census.aim_create", "census returns")
    v = _clean(data, None)
    cols = list(v)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO census_aims ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed column names
            f"VALUES ({', '.join('?' for _ in cols)}, ?, ?)",
            [v[c] for c in cols] + [actor.username, actor.username]).lastrowid
    activity_log.record("census.aim_create", target=aid, principal=actor)
    return get_aim(aid, actor=actor)


def update_aim(aim_id: int, changes: dict[str, Any], *, actor: Principal) -> Aim:
    cur = get_aim(aim_id, actor=actor)
    RC.require_data_manager(actor, "census.aim_update", "census returns")
    v = _clean(changes, cur)
    with database.connect() as conn:
        conn.execute(
            f"UPDATE census_aims SET {', '.join(f'{c} = ?' for c in v)}, "  # nosec B608 - fixed column names
            "updated_by = ?, updated_at = datetime('now') WHERE aim_id = ?",
            [*v.values(), actor.username, cur.aim_id])
    activity_log.record("census.aim_update", target=cur.aim_id, principal=actor)
    return get_aim(cur.aim_id, actor=actor)


def delete_aim(aim_id: int, *, actor: Principal) -> bool:
    cur = get_aim(aim_id, actor=actor)
    RC.require_data_manager(actor, "census.aim_delete", "census returns")
    with database.connect() as conn:
        conn.execute("DELETE FROM census_aims WHERE aim_id = ?", (cur.aim_id,))
    activity_log.record("census.aim_delete", target=cur.aim_id, principal=actor)
    return True


def list_aims(*, actor: Principal, return_id: int | None = None,
              learner_ref: str | None = None, aim_type: str | None = None,
              funding_model: str | None = None, status: str | None = None,
              active_only: bool = False) -> list[Aim]:
    """The old filters. *learner_ref* matches the ref, a linked pupil's
    admission number / UPN, or part of the learner's name."""
    RC.require_data_manager(actor, "census.aims", "census returns")
    where, params = [], []
    for col, val in (("return_id", return_id), ("aim_type", aim_type),
                     ("funding_model", funding_model), ("status", status)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if learner_ref:
        pupil = P.find_by_reference(learner_ref)
        where.append("(lower(learner_ref) = lower(?) OR learner_name LIKE ?"
                     + (" OR pupil_id = ?" if pupil else "") + ")")
        params += [learner_ref.strip(), f"%{learner_ref.strip()}%"]
        if pupil:
            params.append(pupil.pupil_id)
    if active_only:
        where.append("status IN ('Continuing', 'Temporarily Withdrawn')")
    sql = "SELECT * FROM census_aims" + (" WHERE " + " AND ".join(where) if where else "") \
        + " ORDER BY learner_ref COLLATE NOCASE, start_date, aim_id DESC"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, params)]


def aims_for_return(return_id: int, *, actor: Principal) -> list[Aim]:
    return list_aims(actor=actor, return_id=int(return_id))


def aims_for_learner(learner_ref: str, *, actor: Principal) -> list[Aim]:
    return list_aims(actor=actor, learner_ref=learner_ref)


def aims_for_pupil(pupil_id: int, *, actor: Principal) -> list[Aim]:
    RC.require_data_manager(actor, "census.aims", "census returns")
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM census_aims WHERE pupil_id = ? ORDER BY start_date, aim_id",
            (int(pupil_id),))]


def summary(actor: Principal) -> dict[str, Any]:
    """The aim side of the old Summary tab."""
    rows = list_aims(actor=actor)
    st = Counter(a.status for a in rows)
    return {"total": len(rows), "continuing": st["Continuing"],
            "completed": st["Completed"], "withdrawn": st["Withdrawn"],
            "achieved": st["Achieved"], "learners": len({a.learner_ref for a in rows}),
            "by_status": dict(st), "by_type": dict(Counter(a.aim_type for a in rows)),
            "by_funding_model": dict(Counter(a.funding_model for a in rows))}


__all__ = ["AIM_TYPES", "COMPLETION_CODES", "FIELDS", "FUNDING_MODELS", "STATUSES", "Aim",
           "aims_for_learner", "aims_for_pupil", "aims_for_return", "create_aim",
           "delete_aim", "get_aim", "list_aims", "summary", "update_aim"]
