"""Early Warning — at-risk alerts raised against students.

One row per alert. Alerts can be raised manually or by the bundled
``scan(...)`` function which walks the other domain tables
(attendance, behaviour, target setting, etc.) and creates alerts
where measurable thresholds are breached.

Workflow:

    Open  →  Acknowledged  →  Resolved
                            ↘  Dismissed (false positive)

Cascade: deleting a student wipes their alerts.

Optional foreign-key-like fields ``linked_ilp_id`` and
``linked_intervention_id`` carry pointers into those modules — they
aren't enforced at the schema level so the alert can outlive the
target.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.assessment.early_warning import (
    early_warning as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_EARLY_WARNING_DB


ALERT_TYPES: tuple[str, ...] = (
    "Attendance",
    "Punctuality",
    "Behaviour",
    "Academic",
    "Engagement",
    "Homework",
    "Wellbeing",
    "Safeguarding",
    "UCAS / Careers",
    "Multiple",
    "Other",
)
DEFAULT_ALERT_TYPE: str = "Academic"

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY: str = "Medium"

STATUSES: tuple[str, ...] = (
    "Open", "Acknowledged", "Resolved", "Dismissed", "Escalated",
)
DEFAULT_STATUS: str = "Open"
OPEN_STATUSES: tuple[str, ...] = ("Open", "Acknowledged",
                                     "Escalated")

# Sources that an alert can come from — useful for filtering and
# de-duping ``scan(...)`` re-runs.
SOURCES: tuple[str, ...] = (
    "Manual", "Attendance Scan", "Behaviour Scan",
    "Target Scan", "Homework Scan", "Wellbeing Scan",
    "Safeguarding", "Other",
)
DEFAULT_SOURCE: str = "Manual"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Severity ranking used for sort and "stronger than" comparisons.
_SEV_ORDER: dict[str, int] = {
    "Low": 0, "Medium": 1, "High": 2, "Critical": 3,
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS early_warning_alerts (
    alert_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT NOT NULL,
    alert_type            TEXT NOT NULL DEFAULT 'Academic',
    severity              TEXT NOT NULL DEFAULT 'Medium',
    status                TEXT NOT NULL DEFAULT 'Open',
    source                TEXT NOT NULL DEFAULT 'Manual',
    title                 TEXT NOT NULL,
    description           TEXT,
    trigger_metric        TEXT,
    threshold             TEXT,
    raised_on             TEXT NOT NULL,
    raised_by             TEXT,
    acknowledged_on       TEXT,
    acknowledged_by       TEXT,
    resolved_on           TEXT,
    resolved_by           TEXT,
    action_taken          TEXT,
    linked_ilp_id         INTEGER,
    linked_intervention_id INTEGER,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ew_student  ON early_warning_alerts(student_id);
CREATE INDEX IF NOT EXISTS idx_ew_status   ON early_warning_alerts(status);
CREATE INDEX IF NOT EXISTS idx_ew_severity ON early_warning_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_ew_type     ON early_warning_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_ew_raised   ON early_warning_alerts(raised_on);
"""


@dataclass
class Alert:
    alert_id: int
    student_id: str
    alert_type: str
    severity: str
    status: str
    source: str
    title: str
    description: str | None
    trigger_metric: str | None
    threshold: str | None
    raised_on: str
    raised_by: str | None
    acknowledged_on: str | None
    acknowledged_by: str | None
    resolved_on: str | None
    resolved_by: str | None
    action_taken: str | None
    linked_ilp_id: int | None
    linked_intervention_id: int | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def severity_rank(self) -> int:
        return _SEV_ORDER.get(self.severity, 0)

    @property
    def age_days(self) -> int:
        try:
            raised = _dt.date.fromisoformat(self.raised_on)
            return (_dt.date.today() - raised).days
        except ValueError:
            return 0


@dataclass
class AlertRow:
    alert: Alert
    student_name: str


@dataclass
class StudentSummary:
    student_id: str
    total: int
    open_count: int
    critical_open: int
    high_open: int
    by_type: dict[str, int]


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_source: dict[str, int]
    open_count: int
    critical_open: int
    high_open: int
    distinct_students: int
    aged_over_14_days: int      # open alerts >= 14 days old


@dataclass
class ScanResult:
    created: int
    skipped_duplicates: int
    sources: dict[str, int]     # per-source breakdown of created
    # One line per scan source that failed — a failed source is not the
    # same as "no alerts", and callers must say so.
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Early-warning schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Alert:
    return Alert(
        alert_id=r["alert_id"], student_id=r["student_id"],
        alert_type=r["alert_type"], severity=r["severity"],
        status=r["status"], source=r["source"],
        title=r["title"], description=r["description"],
        trigger_metric=r["trigger_metric"],
        threshold=r["threshold"],
        raised_on=r["raised_on"], raised_by=r["raised_by"],
        acknowledged_on=r["acknowledged_on"],
        acknowledged_by=r["acknowledged_by"],
        resolved_on=r["resolved_on"],
        resolved_by=r["resolved_by"],
        action_taken=r["action_taken"],
        linked_ilp_id=r["linked_ilp_id"],
        linked_intervention_id=r["linked_intervention_id"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["title"] = _require(payload.get("title"), "Title").strip()

    atype = (payload.get("alert_type") or DEFAULT_ALERT_TYPE).strip()
    if atype not in ALERT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ALERT_TYPES)}")
    out["alert_type"] = atype

    severity = (payload.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of: {', '.join(SEVERITIES)}")
    out["severity"] = severity

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    source = (payload.get("source") or DEFAULT_SOURCE).strip()
    if source not in SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(SOURCES)}")
    out["source"] = source

    out["raised_on"] = _validate_date(
        payload.get("raised_on"), "Raised on",
        required=False) or _dt.date.today().isoformat()
    out["acknowledged_on"] = _validate_date(
        payload.get("acknowledged_on"), "Acknowledged on")
    out["resolved_on"]     = _validate_date(
        payload.get("resolved_on"), "Resolved on")

    out["description"]    = (payload.get("description")
                                or "").strip() or None
    out["trigger_metric"] = (payload.get("trigger_metric")
                                or "").strip() or None
    out["threshold"]      = (payload.get("threshold")
                                or "").strip() or None
    out["raised_by"]      = (payload.get("raised_by")
                                or "").strip() or None
    out["acknowledged_by"] = (payload.get("acknowledged_by")
                                 or "").strip() or None
    out["resolved_by"]    = (payload.get("resolved_by")
                                or "").strip() or None
    out["action_taken"]   = (payload.get("action_taken")
                                or "").strip() or None
    out["notes"]          = (payload.get("notes")
                                or "").strip() or None

    out["linked_ilp_id"] = None
    if payload.get("linked_ilp_id") not in (None, ""):
        try:
            out["linked_ilp_id"] = int(payload.get("linked_ilp_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "linked_ilp_id must be a number") from None
    out["linked_intervention_id"] = None
    if payload.get("linked_intervention_id") not in (None, ""):
        try:
            out["linked_intervention_id"] = int(
                payload.get("linked_intervention_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "linked_intervention_id must be a number") from None

    today = _dt.date.today().isoformat()
    if status == "Acknowledged" and not out["acknowledged_on"]:
        out["acknowledged_on"] = today
    if (status in ("Resolved", "Dismissed")
            and not out["resolved_on"]):
        out["resolved_on"] = today
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_alert(payload: dict[str, Any]) -> Alert:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO early_warning_alerts
                   (student_id, alert_type, severity, status, source,
                    title, description, trigger_metric, threshold,
                    raised_on, raised_by, acknowledged_on,
                    acknowledged_by, resolved_on, resolved_by,
                    action_taken, linked_ilp_id,
                    linked_intervention_id, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["alert_type"], p["severity"],
             p["status"], p["source"], p["title"],
             p["description"], p["trigger_metric"], p["threshold"],
             p["raised_on"], p["raised_by"],
             p["acknowledged_on"], p["acknowledged_by"],
             p["resolved_on"], p["resolved_by"],
             p["action_taken"], p["linked_ilp_id"],
             p["linked_intervention_id"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_alert(new_id)
    assert out is not None
    logger.info(
        "Raised alert #%d for %s (%s/%s, %s)",
        new_id, p["student_id"], p["alert_type"], p["severity"],
        p["source"])
    return out


def get_alert(alert_id: int) -> Alert | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM early_warning_alerts WHERE alert_id = ?",
            (alert_id,)).fetchone()
        return _row(r) if r else None


def list_alerts(
    *,
    student_id: str | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    source: str | None = None,
    open_only: bool = False,
    min_severity: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    raised_by_like: str | None = None,
    title_like: str | None = None,
) -> list[Alert]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if alert_type:
        if alert_type not in ALERT_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(ALERT_TYPES)}")
        clauses.append("alert_type = ?")
        args.append(alert_type)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: "
                f"{', '.join(SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if source:
        if source not in SOURCES:
            raise ValidationError(
                f"Source must be one of: {', '.join(SOURCES)}")
        clauses.append("source = ?")
        args.append(source)
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if min_severity:
        if min_severity not in SEVERITIES:
            raise ValidationError(
                f"min_severity must be one of: "
                f"{', '.join(SEVERITIES)}")
        cutoff = _SEV_ORDER[min_severity]
        keep = [s for s, n in _SEV_ORDER.items() if n >= cutoff]
        ph = ",".join("?" * len(keep))
        clauses.append(f"severity IN ({ph})")
        args.extend(keep)
    if raised_by_like:
        clauses.append("raised_by LIKE ?")
        args.append(f"%{raised_by_like.strip()}%")
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if date_from:
        clauses.append("raised_on >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("raised_on <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM early_warning_alerts {where} "
           "ORDER BY CASE status "
           "  WHEN 'Open'         THEN 0 "
           "  WHEN 'Escalated'    THEN 1 "
           "  WHEN 'Acknowledged' THEN 2 "
           "  WHEN 'Resolved'     THEN 3 "
           "  WHEN 'Dismissed'    THEN 4 "
           "  ELSE 5 END, "
           "CASE severity "
           "  WHEN 'Critical' THEN 0 "
           "  WHEN 'High'     THEN 1 "
           "  WHEN 'Medium'   THEN 2 "
           "  WHEN 'Low'      THEN 3 "
           "  ELSE 4 END, "
           "raised_on DESC, alert_id DESC")
    with _connect() as conn:
        return [_row(r)
                for r in conn.execute(sql, args).fetchall()]


def list_alerts_with_detail(**kwargs) -> list[AlertRow]:
    rows = list_alerts(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    return [AlertRow(alert=a,
                       student_name=names.get(a.student_id,
                                                "(unknown)"))
            for a in rows]


def update_alert(alert_id: int,
                  payload: dict[str, Any]) -> Alert:
    init_db()
    existing = get_alert(alert_id)
    if existing is None:
        raise ValidationError(f"No alert #{alert_id}")
    merged = {
        "student_id":             existing.student_id,
        "alert_type":             payload.get("alert_type",
                                               existing.alert_type),
        "severity":               payload.get("severity",
                                               existing.severity),
        "status":                 payload.get("status",
                                               existing.status),
        "source":                 payload.get("source",
                                               existing.source),
        "title":                  payload.get("title",
                                               existing.title),
        "description":            payload.get("description",
                                               existing.description),
        "trigger_metric":         payload.get("trigger_metric",
                                               existing.trigger_metric),
        "threshold":              payload.get("threshold",
                                               existing.threshold),
        "raised_on":              payload.get("raised_on",
                                               existing.raised_on),
        "raised_by":              payload.get("raised_by",
                                               existing.raised_by),
        "acknowledged_on":        payload.get("acknowledged_on",
                                               existing.acknowledged_on),
        "acknowledged_by":        payload.get("acknowledged_by",
                                               existing.acknowledged_by),
        "resolved_on":            payload.get("resolved_on",
                                               existing.resolved_on),
        "resolved_by":            payload.get("resolved_by",
                                               existing.resolved_by),
        "action_taken":           payload.get("action_taken",
                                               existing.action_taken),
        "linked_ilp_id":          payload.get("linked_ilp_id",
                                               existing.linked_ilp_id),
        "linked_intervention_id": payload.get(
            "linked_intervention_id",
            existing.linked_intervention_id),
        "notes":                  payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE early_warning_alerts SET
                   alert_type = ?, severity = ?, status = ?,
                   source = ?, title = ?, description = ?,
                   trigger_metric = ?, threshold = ?,
                   raised_on = ?, raised_by = ?,
                   acknowledged_on = ?, acknowledged_by = ?,
                   resolved_on = ?, resolved_by = ?,
                   action_taken = ?, linked_ilp_id = ?,
                   linked_intervention_id = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE alert_id = ?""",
            (p["alert_type"], p["severity"], p["status"],
             p["source"], p["title"], p["description"],
             p["trigger_metric"], p["threshold"],
             p["raised_on"], p["raised_by"],
             p["acknowledged_on"], p["acknowledged_by"],
             p["resolved_on"], p["resolved_by"],
             p["action_taken"], p["linked_ilp_id"],
             p["linked_intervention_id"], p["notes"], alert_id),
        )
        conn.commit()
    out = get_alert(alert_id)
    assert out is not None
    return out


def acknowledge(alert_id: int, *,
                 acknowledged_by: str | None = None) -> Alert:
    today = _dt.date.today().isoformat()
    payload: dict[str, Any] = {
        "status": "Acknowledged",
        "acknowledged_on": today,
    }
    if acknowledged_by is not None:
        payload["acknowledged_by"] = acknowledged_by
    return update_alert(alert_id, payload)


def resolve(alert_id: int, *,
             resolved_by: str | None = None,
             action_taken: str | None = None) -> Alert:
    today = _dt.date.today().isoformat()
    payload: dict[str, Any] = {
        "status": "Resolved",
        "resolved_on": today,
    }
    if resolved_by is not None:
        payload["resolved_by"] = resolved_by
    if action_taken is not None:
        payload["action_taken"] = action_taken
    return update_alert(alert_id, payload)


def dismiss(alert_id: int, *,
             resolved_by: str | None = None,
             reason: str | None = None) -> Alert:
    today = _dt.date.today().isoformat()
    payload: dict[str, Any] = {
        "status": "Dismissed",
        "resolved_on": today,
    }
    if resolved_by is not None:
        payload["resolved_by"] = resolved_by
    if reason is not None:
        payload["action_taken"] = reason
    return update_alert(alert_id, payload)


def escalate(alert_id: int, *,
              raised_by: str | None = None) -> Alert:
    """Bump severity up one notch (capped at Critical) and flag
    status='Escalated'. Used by pastoral leads when an alert isn't
    being acted on."""
    init_db()
    existing = get_alert(alert_id)
    if existing is None:
        raise ValidationError(f"No alert #{alert_id}")
    current = _SEV_ORDER.get(existing.severity, 0)
    next_idx = min(current + 1, len(SEVERITIES) - 1)
    new_severity = next(
        sev for sev, n in _SEV_ORDER.items() if n == next_idx)
    payload: dict[str, Any] = {
        "severity": new_severity,
        "status": "Escalated",
    }
    if raised_by is not None:
        payload["raised_by"] = raised_by
    return update_alert(alert_id, payload)


def set_status(alert_id: int, status: str) -> Alert:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_alert(alert_id, {"status": status})


def delete_alert(alert_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM early_warning_alerts WHERE alert_id = ?",
            (alert_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted alert #%d", alert_id)
            return True
        return False


# ── Per-student lookups ───────────────────────────────────────────

def alerts_for_student(student_id: str) -> list[Alert]:
    return list_alerts(student_id=student_id)


def student_summary(student_id: str) -> StudentSummary:
    init_db()
    rows = alerts_for_student(student_id)
    by_type: dict[str, int] = {}
    open_count = 0
    critical = 0
    high = 0
    for a in rows:
        by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1
        if a.is_open:
            open_count += 1
            if a.severity == "Critical":
                critical += 1
            if a.severity == "High":
                high += 1
    return StudentSummary(
        student_id=student_id,
        total=len(rows),
        open_count=open_count,
        critical_open=critical,
        high_open=high,
        by_type=by_type,
    )


# ── Scanner (auto-raise alerts) ───────────────────────────────────

def _dedupe_key(student_id: str, alert_type: str,
                  source: str) -> str:
    """A stable key the scanner uses to skip re-raising an open
    alert when the same condition is still tripped."""
    return f"{student_id}|{alert_type}|{source}"


def _existing_open_keys() -> set[str]:
    init_db()
    out: set[str] = set()
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT student_id, alert_type, source "
            f"FROM early_warning_alerts WHERE status IN "
            f"({','.join('?' * len(OPEN_STATUSES))})",
            OPEN_STATUSES).fetchall()
    for r in rows:
        out.add(_dedupe_key(r["student_id"],
                              r["alert_type"], r["source"]))
    return out


def scan(
    *,
    raised_by: str | None = "Auto Scanner",
    attendance_window_days: int = 28,
    attendance_min_pct: float = 90.0,
    behaviour_window_days: int = 28,
    behaviour_max_negatives: int = 5,
) -> ScanResult:
    """Walk the available domain tables and auto-raise alerts where
    measurable thresholds are tripped. Safe to re-run — open alerts
    of the same (student × type × source) are skipped so the inbox
    doesn't fill up with duplicates."""
    init_db()
    today = _dt.date.today()
    cutoff_att = (today
                   - _dt.timedelta(days=attendance_window_days)
                   ).isoformat()
    cutoff_beh = (today
                   - _dt.timedelta(days=behaviour_window_days)
                   ).isoformat()
    existing = _existing_open_keys()
    by_source: dict[str, int] = {}
    created = 0
    skipped = 0
    errors: list[str] = []

    # ── Attendance ────────────────────────────────────────────────
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance as _att,
        )
        records = _att.list_records(date_from=cutoff_att,
                                       date_to=today.isoformat())
        agg: dict[str, dict[str, int]] = {}
        for r in records:
            sid = getattr(r, "student_id", None)
            st = getattr(r, "status", None)
            if not sid or not st:
                continue
            d = agg.setdefault(sid, {"Present": 0, "Late": 0,
                                       "Absent": 0,
                                       "Authorised": 0})
            d[st] = d.get(st, 0) + 1
        for sid, d in agg.items():
            total = sum(d.values())
            if total == 0:
                continue
            attending = d.get("Present", 0) + d.get("Late", 0)
            pct = 100.0 * attending / total
            if pct >= attendance_min_pct:
                continue
            key = _dedupe_key(sid, "Attendance",
                                "Attendance Scan")
            if key in existing:
                skipped += 1
                continue
            severity = ("Critical" if pct < attendance_min_pct - 15
                          else "High"
                            if pct < attendance_min_pct - 5
                          else "Medium")
            create_alert({
                "student_id":   sid,
                "alert_type":   "Attendance",
                "severity":     severity,
                "source":       "Attendance Scan",
                "title":        (f"Attendance "
                                  f"{pct:.1f}% (last "
                                  f"{attendance_window_days}d)"),
                "trigger_metric": (
                    f"P={d.get('Present',0)} L={d.get('Late',0)} "
                    f"A={d.get('Absent',0)} "
                    f"Au={d.get('Authorised',0)}"),
                "threshold":     (f"Attendance < "
                                    f"{attendance_min_pct:.0f}%"),
                "raised_by":     raised_by,
                "description":   (f"Auto-raised from attendance "
                                    f"records in the window "
                                    f"{cutoff_att} → {today.isoformat()}."),
            })
            existing.add(key)
            created += 1
            by_source["Attendance Scan"] = (
                by_source.get("Attendance Scan", 0) + 1)
    except Exception as e:
        logger.exception("Attendance scan failed")
        errors.append(f"Attendance scan failed: {type(e).__name__}: {e}")

    # ── Behaviour ─────────────────────────────────────────────────
    try:
        from education_system.systems.sixth_form.domain.pastoral.behaviour import (
            behaviour as _beh,
        )
        rows = _beh.list_entries(date_from=cutoff_beh,
                                    date_to=today.isoformat(),
                                    entry_type="Negative")
        by_student: dict[str, int] = {}
        for r in rows:
            sid = getattr(r, "student_id", None)
            if sid:
                by_student[sid] = by_student.get(sid, 0) + 1
        for sid, n in by_student.items():
            if n <= behaviour_max_negatives:
                continue
            key = _dedupe_key(sid, "Behaviour",
                                "Behaviour Scan")
            if key in existing:
                skipped += 1
                continue
            severity = ("Critical" if n >= behaviour_max_negatives * 2
                          else "High"
                            if n >= behaviour_max_negatives + 3
                          else "Medium")
            create_alert({
                "student_id":   sid,
                "alert_type":   "Behaviour",
                "severity":     severity,
                "source":       "Behaviour Scan",
                "title":        (f"{n} negative behaviour entries "
                                  f"in last {behaviour_window_days}d"),
                "trigger_metric": f"{n} negatives",
                "threshold":     (f"Negatives > "
                                    f"{behaviour_max_negatives}"),
                "raised_by":     raised_by,
                "description":   (f"Auto-raised from behaviour log "
                                    f"in the window "
                                    f"{cutoff_beh} → {today.isoformat()}."),
            })
            existing.add(key)
            created += 1
            by_source["Behaviour Scan"] = (
                by_source.get("Behaviour Scan", 0) + 1)
    except Exception as e:
        logger.exception("Behaviour scan failed")
        errors.append(f"Behaviour scan failed: {type(e).__name__}: {e}")

    # ── Target Setting (Below Target) ─────────────────────────────
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            target_setting as _ts,
        )
        below = _ts.list_targets(at_risk_only=True)
        by_student_below: dict[str, list[str]] = {}
        for t in below:
            if t.status not in ("At Risk", "Below Target"):
                continue
            by_student_below.setdefault(t.student_id, []).append(
                f"{t.subject_name} ({t.status})")
        for sid, subjects in by_student_below.items():
            key = _dedupe_key(sid, "Academic", "Target Scan")
            if key in existing:
                skipped += 1
                continue
            severity = "High" if len(subjects) >= 2 else "Medium"
            create_alert({
                "student_id": sid,
                "alert_type": "Academic",
                "severity":   severity,
                "source":     "Target Scan",
                "title":      (f"Below target in "
                                f"{len(subjects)} subject(s)"),
                "trigger_metric": "; ".join(subjects[:5]),
                "threshold":  "Below MTE − 1 grade",
                "raised_by":  raised_by,
                "description": ("Auto-raised from target_setting; "
                                  "current grade is at risk or below "
                                  "the minimum target."),
            })
            existing.add(key)
            created += 1
            by_source["Target Scan"] = (
                by_source.get("Target Scan", 0) + 1)
    except Exception as e:
        logger.exception("Target-setting scan failed")
        errors.append(f"Target-setting scan failed: {type(e).__name__}: {e}")

    return ScanResult(created=created,
                        skipped_duplicates=skipped,
                        sources=by_source, errors=errors)


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_alerts()
    by_status = {s: 0 for s in STATUSES}
    by_type = {t: 0 for t in ALERT_TYPES}
    by_severity = {s: 0 for s in SEVERITIES}
    by_source = {s: 0 for s in SOURCES}
    open_count = 0
    critical = 0
    high = 0
    aged = 0
    students: set[str] = set()
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1
        by_severity[a.severity] = by_severity.get(
            a.severity, 0) + 1
        by_source[a.source] = by_source.get(a.source, 0) + 1
        students.add(a.student_id)
        if a.is_open:
            open_count += 1
            if a.severity == "Critical":
                critical += 1
            if a.severity == "High":
                high += 1
            if a.age_days >= 14:
                aged += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_severity=by_severity,
        by_source=by_source,
        open_count=open_count,
        critical_open=critical,
        high_open=high,
        distinct_students=len(students),
        aged_over_14_days=aged,
    )


# ── Opening an intervention from an alert ─────────────────────────

# Which intervention type answers which kind of alert.
_ALERT_TO_INTERVENTION: dict[str, str] = {
    "Attendance": "Attendance",
    "Punctuality": "Attendance",
    "Behaviour": "Behaviour",
    "Academic": "Academic Support",
    "Engagement": "Re-engagement",
    "Homework": "Study Skills",
    "Wellbeing": "SEMH",
    "UCAS / Careers": "Careers / Aspirations",
}


def _iv():
    from education_system.systems.sixth_form.domain.assessment.intervention_tracking import (
        intervention_tracking as _intervention_tracking,
    )
    return _intervention_tracking


def linked_intervention(alert_id: int) -> Any:
    """The intervention this alert opened, if it still exists.

    Follows ``linked_intervention_id`` first, then the back-link on the
    intervention side, so a link survives either half being edited.
    """
    alert = get_alert(alert_id)
    if alert is None:
        return None
    iv = _iv()
    if alert.linked_intervention_id is not None:
        found = iv.get_intervention(alert.linked_intervention_id)
        if found is not None:
            return found
    linked = iv.interventions_for_alert(alert_id)
    return linked[0] if linked else None


def open_intervention(alert_id: int, *,
                      title: str | None = None,
                      intervention_type: str | None = None,
                      lead_staff: str | None = None,
                      start_date: str | None = None,
                      actor: str | None = None) -> tuple[Any, bool]:
    """Open an intervention for this alert, or return the one it already
    opened. Returns ``(intervention, created)``.

    Idempotent: asking twice never creates a second intervention. The
    alert is linked (``linked_intervention_id``), the intervention is
    back-linked (``early_warning_alert_id``) and an Open alert moves to
    Acknowledged with the action recorded.
    """
    init_db()
    alert = get_alert(alert_id)
    if alert is None:
        raise ValidationError(f"No alert #{alert_id}")
    iv = _iv()
    existing = linked_intervention(alert_id)
    if existing is not None:
        # Repair whichever half of the link is missing.
        if alert.linked_intervention_id != existing.intervention_id:
            update_alert(alert_id, {
                "linked_intervention_id": existing.intervention_id})
        if iv.source_alert_id(existing.intervention_id) != alert_id:
            iv.set_source_alert(existing.intervention_id, alert_id)
        return existing, False
    if alert.status in ("Resolved", "Dismissed"):
        raise ValidationError(
            f"Alert #{alert_id} is {alert.status} — reopen it before "
            "starting an intervention")

    itype = intervention_type or _ALERT_TO_INTERVENTION.get(
        alert.alert_type, iv.DEFAULT_INTERVENTION_TYPE)
    try:
        created = iv.create_intervention({
            "student_id": alert.student_id,
            "title": title or f"{alert.alert_type}: {alert.title}"[:200],
            "intervention_type": itype,
            "lead_staff": lead_staff,
            "start_date": start_date or _dt.date.today().isoformat(),
            "status": "Planned",
            "referral_source": f"Early Warning alert #{alert_id}",
            "rationale": alert.description or alert.title,
            "baseline_indicator": (
                f"{alert.trigger_metric}: {alert.threshold}"
                if alert.trigger_metric else None),
        })
    except iv.ValidationError as e:
        raise ValidationError(str(e)) from None
    iv.set_source_alert(created.intervention_id, alert_id)

    note = f"Intervention #{created.intervention_id} opened"
    payload: dict[str, Any] = {
        "linked_intervention_id": created.intervention_id,
        "action_taken": (f"{alert.action_taken}; {note}"
                         if alert.action_taken else note),
    }
    if alert.status == "Open":
        payload["status"] = "Acknowledged"
        payload["acknowledged_on"] = _dt.date.today().isoformat()
        if actor:
            payload["acknowledged_by"] = actor
    update_alert(alert_id, payload)
    logger.info("Alert #%d opened intervention #%d", alert_id,
                created.intervention_id)
    return created, True


def link_intervention(alert_id: int, intervention_id: int) -> Alert:
    """Link an alert to an intervention that already exists."""
    init_db()
    alert = get_alert(alert_id)
    if alert is None:
        raise ValidationError(f"No alert #{alert_id}")
    iv = _iv()
    target = iv.get_intervention(intervention_id)
    if target is None:
        raise ValidationError(f"No intervention #{intervention_id}")
    if target.student_id != alert.student_id:
        raise ValidationError(
            "That intervention belongs to a different student")
    iv.set_source_alert(intervention_id, alert_id)
    return update_alert(alert_id,
                        {"linked_intervention_id": intervention_id})
