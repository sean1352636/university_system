"""Module specification and change control.

A module record used to be edited in place with no trace: whoever opened the
form last decided what the module was. Here every applied change is written
to ``module_change_history`` field by field, and a module leader who may not
edit the catalogue can *propose* a change, which a catalogue manager approves
or rejects. Approval re-checks each field still holds the value the proposal
was based on, so an approval never silently overwrites a later edit.

The specification (aims, content, teaching methods, study hours, reading
list), the module's learning outcomes and its planned assessment pattern all
go through the same path: change keys are ``module_name``-style for columns
of ``modules`` and ``spec.<field>`` for ``module_specifications``.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
from datetime import datetime

from education_system.systems.university.infrastructure.database.schemas import (
    module_catalogue_schema as schema,
)

MODULE_FIELDS = ("module_name", "module_type", "credits", "level", "semester", "year",
                 "course", "department", "capacity", "description")
SPEC_FIELDS = ("aims", "indicative_content", "teaching_methods", "contact_hours",
               "independent_study_hours", "placement_hours", "reading_list")
HOUR_FIELDS = ("contact_hours", "independent_study_hours", "placement_hours")
LEVELS = (3, 4, 5, 6, 7, 8)
#: UK convention: one credit is ten notional hours of learning.
HOURS_PER_CREDIT = 10
BLOOM_LEVELS = ("remember", "understand", "apply", "analyse", "evaluate", "create")

FIELD_LABELS = {
    "module_name": "Name", "module_type": "Type", "credits": "Credits", "level": "Level",
    "semester": "Semester", "year": "Year of study", "course": "Course",
    "department": "Department", "capacity": "Capacity", "description": "Description",
    "spec.aims": "Aims", "spec.indicative_content": "Indicative content",
    "spec.teaching_methods": "Teaching methods", "spec.contact_hours": "Contact hours",
    "spec.independent_study_hours": "Independent study hours",
    "spec.placement_hours": "Placement hours", "spec.reading_list": "Reading list",
}


def ensure(conn):
    schema.apply_to_connection(conn)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _text(value):
    return None if value is None else str(value)


# ── reading ─────────────────────────────────────────────────────────────


def get_spec(conn, code) -> dict:
    ensure(conn)
    cur = conn.execute(f"SELECT {', '.join(SPEC_FIELDS)}, updated_by, updated_at "
                       "FROM module_specifications WHERE module_code = ?", (code,))
    row = cur.fetchone()
    names = [d[0] for d in cur.description]
    return dict(zip(names, tuple(row))) if row else dict.fromkeys(names)


def current_values(conn, code) -> dict:
    """Every editable value of the module, keyed as changes are."""
    ensure(conn)
    cur = conn.execute(f"SELECT {', '.join(MODULE_FIELDS)} FROM modules WHERE module_code = ?",
                       (code,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"Module {code} does not exist")
    values = dict(zip(MODULE_FIELDS, tuple(row)))
    spec = get_spec(conn, code)
    values.update({f"spec.{f}": spec.get(f) for f in SPEC_FIELDS})
    return values


# ── validation ──────────────────────────────────────────────────────────


def _number(key, value, *, integer=False, low=0, high=None):
    if value in (None, ""):
        return None
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{FIELD_LABELS.get(key, key)} must be a number") from None
    if number < low or (high is not None and number > high):
        bound = f"between {low} and {high}" if high is not None else f"at least {low}"
        raise ValueError(f"{FIELD_LABELS.get(key, key)} must be {bound}")
    return number


def clean_changes(changes: dict) -> dict:
    """Validated, normalised copy of *changes*. Unknown keys are refused."""
    out = {}
    for key, value in changes.items():
        if key not in FIELD_LABELS:
            raise ValueError(f"{key} cannot be changed here")
        if isinstance(value, str):
            value = value.strip() or None
        if key == "credits":
            value = _number(key, value, integer=True, high=180)
        elif key == "capacity":
            value = _number(key, value, integer=True) or None
        elif key == "level":
            value = _number(key, value, integer=True, low=3, high=8)
        elif key.startswith("spec.") and key[5:] in HOUR_FIELDS:
            value = _number(key, value)
        if key == "module_name" and not value:
            raise ValueError("Name is required")
        out[key] = value
    return out


def diff(conn, code, changes: dict) -> dict:
    """``{key: (old, new)}`` for the values that actually change."""
    current = current_values(conn, code)
    out = {}
    for key, new in clean_changes(changes).items():
        old = current.get(key)
        if _text(old) != _text(new) and not (old in (None, "") and new in (None, "")):
            out[key] = (old, new)
    return out


# ── applying ────────────────────────────────────────────────────────────


def _write(conn, code, values: dict, actor):
    module = {k: v for k, v in values.items() if k in MODULE_FIELDS}
    spec = {k[5:]: v for k, v in values.items() if k.startswith("spec.")}
    if module:
        sets = ", ".join(f"{k} = ?" for k in module)
        # db-audit: ignore[DBW001] - keys are checked against MODULE_FIELDS
        conn.execute(f"UPDATE modules SET {sets}, updated_at = ? WHERE module_code = ?",
                     (*module.values(), _now(), code))
    if spec:
        conn.execute("INSERT OR IGNORE INTO module_specifications (module_code) VALUES (?)",
                     (code,))
        sets = ", ".join(f"{k} = ?" for k in spec)
        # db-audit: ignore[DBW001] - keys are checked against SPEC_FIELDS
        conn.execute(f"UPDATE module_specifications SET {sets}, updated_by = ?, updated_at = ? "
                     "WHERE module_code = ?", (*spec.values(), actor, _now(), code))


def _record(conn, code, changed: dict, actor, request_id=None):
    conn.executemany(
        "INSERT INTO module_change_history "
        "(module_code, field, old_value, new_value, changed_by, request_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(code, key, _text(old), _text(new), actor, request_id)
         for key, (old, new) in changed.items()])


def apply_changes(conn, code, changes: dict, actor, request_id=None) -> dict:
    """Write *changes* and record each changed field. Returns the diff."""
    ensure(conn)
    changed = diff(conn, code, changes)
    if changed:
        _write(conn, code, {k: new for k, (_old, new) in changed.items()}, actor)
        _record(conn, code, changed, actor, request_id)
    return changed


def record_created(conn, code, values: dict, actor):
    """History for a newly added module: one 'created' line plus its values."""
    ensure(conn)
    changed = {"created": (None, code)}
    changed.update({k: (None, v) for k, v in values.items()
                    if k in FIELD_LABELS and v not in (None, "")})
    _record(conn, code, changed, actor)


# ── change requests ─────────────────────────────────────────────────────


def propose_change(conn, code, changes: dict, actor, summary) -> int:
    ensure(conn)
    if not (summary or "").strip():
        raise ValueError("Say what the change is and why")
    changed = diff(conn, code, changes)
    if not changed:
        raise ValueError("Nothing would change")
    pending = conn.execute("SELECT id FROM module_change_requests WHERE module_code = ? "
                           "AND status = 'pending' AND proposed_by = ?", (code, actor)).fetchone()
    if pending:
        raise ValueError(f"You already have change request #{pending[0]} pending for {code}; "
                         "withdraw it first")
    payload = {k: [old, new] for k, (old, new) in changed.items()}
    cur = conn.execute("INSERT INTO module_change_requests "
                       "(module_code, summary, changes_json, proposed_by) VALUES (?, ?, ?, ?)",
                       (code, summary.strip(), json.dumps(payload, default=str), actor))
    return int(cur.lastrowid)


def _request(conn, request_id):
    cur = conn.execute("SELECT * FROM module_change_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No change request #{request_id}")
    out = dict(zip([d[0] for d in cur.description], tuple(row)))
    out["changes"] = json.loads(out["changes_json"] or "{}")
    return out


def list_requests(conn, code=None, status="pending") -> list[dict]:
    ensure(conn)
    sql, params = "SELECT id FROM module_change_requests WHERE 1 = 1", []
    if code:
        sql += " AND module_code = ?"
        params.append(code)
    if status:
        sql += " AND status = ?"
        params.append(status)
    ids = [r[0] for r in conn.execute(sql + " ORDER BY id DESC", params)]
    return [_request(conn, i) for i in ids]


def decide_request(conn, request_id, approve: bool, actor, note=None) -> dict:
    """Approve (apply) or reject a pending request. Returns the request."""
    ensure(conn)
    req = _request(conn, request_id)
    if req["status"] != "pending":
        raise ValueError(f"Request #{request_id} is already {req['status']}")
    if req["proposed_by"] == actor:
        raise ValueError("A change cannot be approved or rejected by the person who proposed it")
    if not approve and not (note or "").strip():
        raise ValueError("Give a reason for rejecting it")
    if approve:
        current = current_values(conn, req["module_code"])
        stale = [FIELD_LABELS.get(k, k) for k, (old, _new) in req["changes"].items()
                 if _text(current.get(k)) != _text(old)]
        if stale:
            raise ValueError("The module has changed since this was proposed ("
                             + ", ".join(stale) + "); ask for a fresh proposal")
        apply_changes(conn, req["module_code"],
                      {k: new for k, (_old, new) in req["changes"].items()}, actor, request_id)
    conn.execute("UPDATE module_change_requests SET status = ?, decided_by = ?, decided_at = ?, "
                 "decision_note = ? WHERE id = ?",
                 ("approved" if approve else "rejected", actor, _now(),
                  (note or "").strip() or None, request_id))
    return _request(conn, request_id)


def withdraw_request(conn, request_id, actor):
    req = _request(conn, request_id)
    if req["status"] != "pending":
        raise ValueError(f"Request #{request_id} is already {req['status']}")
    if req["proposed_by"] != actor:
        raise ValueError("Only the person who proposed a change can withdraw it")
    conn.execute("UPDATE module_change_requests SET status = 'withdrawn', decided_at = ? "
                 "WHERE id = ?", (_now(), request_id))
    return True


def history(conn, code, limit=300) -> list[dict]:
    ensure(conn)
    cur = conn.execute("SELECT changed_at, field, old_value, new_value, changed_by, request_id "
                       "FROM module_change_history WHERE module_code = ? "
                       "ORDER BY id DESC LIMIT ?", (code, limit))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


# ── learning outcomes ───────────────────────────────────────────────────


def list_outcomes(conn, code) -> list[dict]:
    ensure(conn)
    cur = conn.execute("SELECT outcome_id, outcome_code, description, bloom_level "
                       "FROM learning_outcomes WHERE module_code = ? "
                       "AND COALESCE(outcome_type, 'module') = 'module' "
                       "ORDER BY outcome_code", (code,))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _next_outcome_code(conn, code):
    used = {r["outcome_code"] for r in list_outcomes(conn, code)}
    n = 1
    while f"LO{n}" in used:
        n += 1
    return f"LO{n}"


def add_outcome(conn, code, description, bloom_level="understand", actor=None) -> str:
    description = (description or "").strip()
    if not description:
        raise ValueError("Describe what a student will be able to do")
    if bloom_level not in BLOOM_LEVELS:
        raise ValueError(f"Level of learning must be one of: {', '.join(BLOOM_LEVELS)}")
    level = conn.execute("SELECT level FROM modules WHERE module_code = ?", (code,)).fetchone()
    if level is None:
        raise ValueError(f"Module {code} does not exist")
    outcome_code = _next_outcome_code(conn, code)
    conn.execute("INSERT INTO learning_outcomes (outcome_code, code, description, level, "
                 "module_code, bloom_level, outcome_type, category) "
                 "VALUES (?, ?, ?, ?, ?, ?, 'module', 'module')",
                 (outcome_code, outcome_code, description, level[0], code, bloom_level))
    _record(conn, code, {f"outcome {outcome_code}": (None, description)}, actor)
    return outcome_code


def delete_outcome(conn, code, outcome_id, actor=None):
    row = conn.execute("SELECT outcome_code, description FROM learning_outcomes "
                       "WHERE outcome_id = ? AND module_code = ?", (outcome_id, code)).fetchone()
    if row is None:
        raise ValueError("That outcome is not on this module")
    conn.execute("DELETE FROM learning_outcomes WHERE outcome_id = ?", (outcome_id,))
    _record(conn, code, {f"outcome {row[0]}": (row[1], None)}, actor)


# ── assessment plan ─────────────────────────────────────────────────────


def list_plan(conn, code) -> list[dict]:
    ensure(conn)
    cur = conn.execute("SELECT id, component, assessment_type, weight, size, outcomes "
                       "FROM module_assessment_plan WHERE module_code = ? "
                       "ORDER BY sort_order, id", (code,))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _outcome_codes(text) -> list[str]:
    return [c.strip().upper() for c in (text or "").replace(";", ",").split(",") if c.strip()]


def add_component(conn, code, component, assessment_type, weight, size=None,
                  outcomes=None, actor=None) -> int:
    ensure(conn)
    component = (component or "").strip()
    if not component:
        raise ValueError("Name the assessment component")
    weight = _number("weight", weight, low=0.01, high=100)
    if weight is None:
        raise ValueError("Give the component a weighting")
    known = {o["outcome_code"].upper() for o in list_outcomes(conn, code)}
    unknown = [c for c in _outcome_codes(outcomes) if c not in known]
    if unknown:
        raise ValueError(f"Not outcomes of this module: {', '.join(unknown)}")
    total = sum(p["weight"] for p in list_plan(conn, code)) + weight
    if total > 100.001:
        raise ValueError(f"Weightings would total {total:g}%; the plan cannot exceed 100%")
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM module_assessment_plan "
                         "WHERE module_code = ?", (code,)).fetchone()[0]
    cur = conn.execute("INSERT INTO module_assessment_plan (module_code, component, "
                       "assessment_type, weight, size, outcomes, sort_order) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (code, component, (assessment_type or "").strip() or None, weight,
                        (size or "").strip() or None, ", ".join(_outcome_codes(outcomes)) or None,
                        order))
    _record(conn, code, {f"assessment plan: {component}": (None, f"{weight:g}%")}, actor)
    return int(cur.lastrowid)


def delete_component(conn, code, component_id, actor=None):
    row = conn.execute("SELECT component, weight FROM module_assessment_plan "
                       "WHERE id = ? AND module_code = ?", (component_id, code)).fetchone()
    if row is None:
        raise ValueError("That component is not on this module")
    conn.execute("DELETE FROM module_assessment_plan WHERE id = ?", (component_id,))
    _record(conn, code, {f"assessment plan: {row[0]}": (f"{row[1]:g}%", None)}, actor)


# ── checks ──────────────────────────────────────────────────────────────


def _hours_issue(spec, credits):
    hours = [spec.get(f) for f in HOUR_FIELDS]
    if not credits or all(h is None for h in hours):
        return None
    total, expected = sum(h or 0 for h in hours), credits * HOURS_PER_CREDIT
    if abs(total - expected) > 0.5:
        return (f"study hours total {total:g}, but {credits} credits means "
                f"{expected} notional hours")
    return None


def spec_issues(conn, code) -> list[str]:
    """What is missing or inconsistent in the module's specification."""
    values = current_values(conn, code)
    spec = get_spec(conn, code)
    issues = [f"no {label.lower()}" for f, label in
              (("aims", "Aims"), ("teaching_methods", "Teaching methods")) if not spec.get(f)]
    if not values.get("level"):
        issues.append("no FHEQ level")
    hours = _hours_issue(spec, values.get("credits") or 0)
    if hours:
        issues.append(hours)
    outcomes = {o["outcome_code"].upper() for o in list_outcomes(conn, code)}
    plan = list_plan(conn, code)
    if not outcomes:
        issues.append("no learning outcomes")
    if plan and abs(sum(p["weight"] for p in plan) - 100) > 0.01:
        issues.append(f"assessment plan totals {sum(p['weight'] for p in plan):g}%, not 100%")
    assessed = {c for p in plan for c in _outcome_codes(p["outcomes"])}
    if plan and outcomes - assessed:
        issues.append("outcomes not assessed by any component: "
                      + ", ".join(sorted(outcomes - assessed)))
    return issues
