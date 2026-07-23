"""Automation rules engine for the Sixth Form System.

A lightweight "if this, then flag that" engine. Staff define **rules**
from a fixed catalogue of triggers — each a measurable condition on a
student (attendance, behaviour, grade gaps, risk score) — and when the
engine runs it evaluates every active student and raises an **action**
(a worklist item) for each match.

Why a fixed trigger catalogue rather than a free-text DSL? It keeps the
engine safe (no arbitrary code/SQL), explainable to non-technical staff
and reuses the existing :mod:`risk_analytics` assessment so a single
pass over a student yields every signal a rule might test.

Actions land in ``automation_actions`` with a status workflow
(Open → Done / Dismissed). Re-running the engine is idempotent: a rule
that already has an *Open* action for a student won't duplicate it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.assessment.risk_analytics import (
    risk_analytics,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.AUTOMATION_RULES_DB

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
ACTION_STATUSES: tuple[str, ...] = ("Open", "Done", "Dismissed")


@dataclass(frozen=True)
class TriggerDef:
    key: str
    label: str
    unit: str                       # how to read the threshold
    # Given a RiskAssessment and threshold, return (matched, detail).
    evaluate: Callable[["risk_analytics.RiskAssessment", float], tuple[bool, str]]


def _t_attendance(a, thr: float):
    if a.attendance_pct is None:
        return False, ""
    return a.attendance_pct < thr, f"attendance {a.attendance_pct}% < {thr}%"


def _t_behaviour(a, thr: float):
    return a.behaviour_points >= thr, f"{a.behaviour_points} net negative points ≥ {int(thr)}"


def _t_risk(a, thr: float):
    return a.score >= thr, f"risk score {a.score} ≥ {thr}"


def _count_pred_below_target(a) -> int:
    gp = risk_analytics.GRADE_POINTS
    return sum(1 for p in a.predictions
              if p.predicted_grade in gp and p.target_grade in gp
              and gp[p.predicted_grade] < gp[p.target_grade])


def _count_mock_below_pred(a) -> int:
    gp = risk_analytics.GRADE_POINTS
    return sum(1 for p in a.predictions
              if p.latest_mock_grade in gp and p.predicted_grade in gp
              and gp[p.latest_mock_grade] < gp[p.predicted_grade])


def _t_pred_below(a, thr: float):
    n = _count_pred_below_target(a)
    return n >= thr, f"{n} subject(s) predicted below target ≥ {int(thr)}"


def _t_mock_below(a, thr: float):
    n = _count_mock_below_pred(a)
    return n >= thr, f"{n} subject(s) with mock below prediction ≥ {int(thr)}"


TRIGGERS: tuple[TriggerDef, ...] = (
    TriggerDef("attendance_below", "Attendance below %", "percent", _t_attendance),
    TriggerDef("behaviour_points", "Net negative behaviour points ≥", "points", _t_behaviour),
    TriggerDef("risk_score", "Risk score ≥", "score", _t_risk),
    TriggerDef("predicted_below_target", "Subjects predicted below target ≥", "count", _t_pred_below),
    TriggerDef("mock_below_predicted", "Subjects with mock below prediction ≥", "count", _t_mock_below),
)
_TRIGGER_BY_KEY = {t.key: t for t in TRIGGERS}


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS automation_rules (
    rule_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    trigger_key  TEXT NOT NULL,
    threshold    REAL NOT NULL,
    window_days  INTEGER NOT NULL DEFAULT 90,
    action_label TEXT NOT NULL,
    severity     TEXT NOT NULL DEFAULT 'Medium',
    enabled      INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    last_run_at  TEXT,
    last_matches INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS automation_actions (
    action_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id     INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'Medium',
    status      TEXT NOT NULL DEFAULT 'Open',
    created_at  TEXT DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by TEXT,
    FOREIGN KEY (rule_id)    REFERENCES automation_rules(rule_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)      ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_autoact_status ON automation_actions(status);
CREATE INDEX IF NOT EXISTS idx_autoact_rule   ON automation_actions(rule_id);
"""

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    risk_analytics.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("Automation-rules schema ready at %s", DB_PATH)


class ValidationError(ValueError):
    """Raised for invalid rule input."""


# ── Rule CRUD ────────────────────────────────────────────────────────

def create_rule(*, name: str, trigger_key: str, threshold: float,
                action_label: str, severity: str = "Medium",
                window_days: int = 90, notes: str = "") -> int:
    init_db()
    if not name.strip():
        raise ValidationError("Rule name is required")
    if trigger_key not in _TRIGGER_BY_KEY:
        raise ValidationError(f"Unknown trigger: {trigger_key}")
    if severity not in SEVERITIES:
        raise ValidationError(f"Severity must be one of: {', '.join(SEVERITIES)}")
    if not action_label.strip():
        raise ValidationError("Action label is required")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO automation_rules "
            "(name, trigger_key, threshold, window_days, action_label, severity, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (name.strip(), trigger_key, float(threshold), int(window_days),
             action_label.strip(), severity, notes or None))
        conn.commit()
        return cur.lastrowid


def set_enabled(rule_id: int, enabled: bool) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE automation_rules SET enabled=? WHERE rule_id=?",
                     (1 if enabled else 0, rule_id))
        conn.commit()


def delete_rule(rule_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM automation_rules WHERE rule_id=?", (rule_id,))
        conn.commit()


def list_rules() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM automation_rules ORDER BY rule_id").fetchall()
    out = []
    for r in rows:
        td = _TRIGGER_BY_KEY.get(r["trigger_key"])
        out.append({
            "rule_id": r["rule_id"], "name": r["name"],
            "trigger_key": r["trigger_key"],
            "trigger_label": td.label if td else r["trigger_key"],
            "threshold": r["threshold"], "window_days": r["window_days"],
            "action_label": r["action_label"], "severity": r["severity"],
            "enabled": bool(r["enabled"]), "notes": r["notes"],
            "last_run_at": r["last_run_at"], "last_matches": r["last_matches"],
        })
    return out


# ── Engine ───────────────────────────────────────────────────────────

def run_rules(*, rule_id: int | None = None) -> dict[str, Any]:
    """Evaluate enabled rules against every active student.

    One :func:`risk_analytics.assess_student` call per student feeds all
    rules, so the cost is one pass regardless of rule count. New matches
    become Open actions; existing Open actions for the same (rule,
    student) are left untouched (idempotent).
    """
    init_db()
    rules = [r for r in list_rules() if r["enabled"]
             and (rule_id is None or r["rule_id"] == rule_id)]
    if not rules:
        return {"rules_run": 0, "new_actions": 0}

    with risk_analytics._connect() as rconn:  # reuse one connection
        student_ids = risk_analytics._active_student_ids(rconn)

    new_actions = 0
    per_rule_counts: dict[int, int] = {r["rule_id"]: 0 for r in rules}
    now = _dt.datetime.now().isoformat(timespec="seconds")

    with _connect() as conn:
        for sid in student_ids:
            try:
                assessment = risk_analytics.assess_student(sid)
            except Exception:
                logger.exception("Assessment failed for %s during rule run", sid)
                continue
            for r in rules:
                td = _TRIGGER_BY_KEY.get(r["trigger_key"])
                if not td:
                    continue
                matched, detail = td.evaluate(assessment, r["threshold"])
                if not matched:
                    continue
                per_rule_counts[r["rule_id"]] += 1
                # Idempotent: skip if an Open action already exists.
                exists = conn.execute(
                    "SELECT 1 FROM automation_actions "
                    "WHERE rule_id=? AND student_id=? AND status='Open'",
                    (r["rule_id"], sid)).fetchone()
                if exists:
                    continue
                message = f"{r['action_label']} — {assessment.full_name}: {detail}"
                conn.execute(
                    "INSERT INTO automation_actions "
                    "(rule_id, student_id, message, severity) VALUES (?,?,?,?)",
                    (r["rule_id"], sid, message, r["severity"]))
                new_actions += 1
        for r in rules:
            conn.execute(
                "UPDATE automation_rules SET last_run_at=?, last_matches=? WHERE rule_id=?",
                (now, per_rule_counts[r["rule_id"]], r["rule_id"]))
        conn.commit()

    logger.info("Automation run: %d rules, %d new actions", len(rules), new_actions)
    return {"rules_run": len(rules), "new_actions": new_actions,
            "matches": sum(per_rule_counts.values())}


# ── Action worklist ──────────────────────────────────────────────────

def list_actions(*, status: str = "Open", limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT a.*, r.name AS rule_name, st.first_name, st.last_name
              FROM automation_actions a
              JOIN automation_rules r ON r.rule_id = a.rule_id
              JOIN students st        ON st.student_id = a.student_id
             WHERE (? = '' OR a.status = ?)
             ORDER BY CASE a.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                                      WHEN 'Medium' THEN 2 ELSE 3 END,
                      a.created_at DESC
             LIMIT ?
            """,
            (status, status, limit)).fetchall()
    return [{
        "action_id": r["action_id"], "rule_id": r["rule_id"], "rule_name": r["rule_name"],
        "student_id": r["student_id"],
        "full_name": f"{r['first_name']} {r['last_name']}".strip(),
        "message": r["message"], "severity": r["severity"], "status": r["status"],
        "created_at": r["created_at"], "resolved_at": r["resolved_at"],
        "resolved_by": r["resolved_by"],
    } for r in rows]


def resolve_action(action_id: int, *, status: str = "Done", by: str = "") -> None:
    init_db()
    if status not in ACTION_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(ACTION_STATUSES)}")
    resolved_at = _dt.datetime.now().isoformat(timespec="seconds") if status != "Open" else None
    with _connect() as conn:
        conn.execute(
            "UPDATE automation_actions SET status=?, resolved_at=?, resolved_by=? "
            "WHERE action_id=?", (status, resolved_at, by or None, action_id))
        conn.commit()
