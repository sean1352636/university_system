"""Audit Reports for the Secondary School System.

Canned, read-only reports built on top of the ``activity_feed`` event
log. Useful for compliance / safeguarding sign-off, governor packs and
incident reviews.

What's stored locally
---------------------
* ``audit_report_defs``  — user-saved report definitions (type +
  default filters + a friendly name).
* ``audit_report_runs``  — snapshots of run results (frozen rows so
  the same numbers can be re-printed weeks later).

The actual events live in the ``activity_feed`` table — this module
queries that table, never mutates it.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from education_system.secondarysch_system.core import paths
from education_system.secondarysch_system.modules.domain.staff_comms.activity_feed import (
    activity_feed as _af,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.AUDIT_REPORTS_DB


# Report-type catalogue. Each key maps to a builder function below.
REPORT_TYPES: tuple[str, ...] = (
    "actions_by_user",
    "actions_by_type",
    "events_timeline",
    "deletes",
    "security_events",
    "failed_logins",
    "severity_breakdown",
    "daily_summary",
    "entity_history",
    "source_breakdown",
)

REPORT_LABELS: dict[str, str] = {
    "actions_by_user":     "Actions by user",
    "actions_by_type":     "Actions by action type",
    "events_timeline":     "Events timeline",
    "deletes":             "Deletions",
    "security_events":     "Security events",
    "failed_logins":       "Failed logins",
    "severity_breakdown":  "Severity breakdown",
    "daily_summary":       "Daily summary",
    "entity_history":      "Entity history",
    "source_breakdown":    "Source breakdown",
}

REPORT_DESCRIPTIONS: dict[str, str] = {
    "actions_by_user":
        "Count of events by actor over a date window.",
    "actions_by_type":
        "Count of events grouped by action verb.",
    "events_timeline":
        "Flat list of events for the chosen window/filter.",
    "deletes":
        "Every delete recorded in the period — useful for incident "
        "reviews and undelete decisions.",
    "security_events":
        "Logins, logouts, failed logins, and any 'warning' / 'error' "
        "severity events.",
    "failed_logins":
        "Just the failed login attempts (login_failed).",
    "severity_breakdown":
        "Counts grouped by severity (info / audit / warning / error).",
    "daily_summary":
        "Per-day event counts over the chosen window.",
    "entity_history":
        "Every event recorded against a specific entity (e.g. one "
        "student or one staff record).",
    "source_breakdown":
        "Counts grouped by source (cli / gui / api / system / "
        "background).",
}

EXPORT_FORMATS: tuple[str, ...] = ("csv", "tsv", "json", "markdown")
DEFAULT_EXPORT_FORMAT: str = "csv"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── DB plumbing ────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_report_defs (
    def_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    report_type   TEXT NOT NULL,
    description   TEXT,
    filters_json  TEXT NOT NULL DEFAULT '{}',
    created_by    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_report_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    def_id        INTEGER,
    report_type   TEXT NOT NULL,
    name          TEXT NOT NULL,
    filters_json  TEXT NOT NULL DEFAULT '{}',
    headers_json  TEXT NOT NULL,
    rows_json     TEXT NOT NULL,
    row_count     INTEGER NOT NULL,
    run_by        TEXT,
    run_at        TEXT DEFAULT (datetime('now')),
    notes         TEXT,
    FOREIGN KEY (def_id) REFERENCES audit_report_defs(def_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ar_defs_type ON audit_report_defs(report_type);
CREATE INDEX IF NOT EXISTS idx_ar_runs_at   ON audit_report_runs(run_at DESC);
CREATE INDEX IF NOT EXISTS idx_ar_runs_type ON audit_report_runs(report_type);
CREATE INDEX IF NOT EXISTS idx_ar_runs_def  ON audit_report_runs(def_id);
"""


def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _af.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Audit-reports schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Types ─────────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class ReportDef:
    def_id: int
    name: str
    report_type: str
    description: str | None
    filters: dict[str, Any]
    created_by: str | None
    created_at: str
    updated_at: str

    @property
    def type_label(self) -> str:
        return REPORT_LABELS.get(self.report_type, self.report_type)


@dataclass
class ReportResult:
    report_type: str
    name: str
    headers: list[str]
    rows: list[list[Any]]
    filters: dict[str, Any]
    generated_at: str

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def label(self) -> str:
        return REPORT_LABELS.get(self.report_type, self.report_type)


@dataclass
class ReportRun:
    run_id: int
    def_id: int | None
    report_type: str
    name: str
    filters: dict[str, Any]
    headers: list[str]
    rows: list[list[Any]]
    row_count: int
    run_by: str | None
    run_at: str
    notes: str | None

    def as_result(self) -> ReportResult:
        return ReportResult(
            report_type=self.report_type, name=self.name,
            headers=list(self.headers), rows=list(self.rows),
            filters=dict(self.filters), generated_at=self.run_at,
        )


# ── Validation ────────────────────────────────────────────────────

def _now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _require(v: Any, label: str) -> Any:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_report_type(v: Any) -> str:
    s = _require(v, "Report type")
    s = str(s).strip()
    if s not in REPORT_TYPES:
        raise ValidationError(
            f"Report type must be one of: {', '.join(REPORT_TYPES)}")
    return s


def _validate_date(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    # Allow either YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS].
    if not (_DATE_RE.match(s)
            or re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", s)):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _normalise_filters(report_type: str,
                       filters: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce / validate the filter dict to the keys this report
    type understands. Unknown keys are dropped (kept as a soft
    behaviour so saved defs survive code changes)."""
    f = dict(filters or {})
    out: dict[str, Any] = {}
    df = _validate_date(f.get("date_from"), "date_from")
    dt = _validate_date(f.get("date_to"), "date_to")
    if df:
        out["date_from"] = df
    if dt:
        out["date_to"] = dt
    for k in ("actor", "action", "entity_type", "entity_id",
              "severity", "source", "summary_like"):
        v = f.get(k)
        if v in (None, "") or (isinstance(v, str) and not v.strip()):
            continue
        out[k] = str(v).strip()
    # Pass-through ints.
    lim = f.get("limit")
    if lim not in (None, ""):
        try:
            out["limit"] = max(1, min(10000, int(lim)))
        except (TypeError, ValueError):
            raise ValidationError("limit must be a whole number") from None
    if report_type == "entity_history":
        # Entity history needs at minimum an entity_id.
        if not out.get("entity_id"):
            raise ValidationError(
                "entity_history requires an entity_id filter")
    return out


# ── Report definition CRUD ────────────────────────────────────────

def _row_def(r: sqlite3.Row) -> ReportDef:
    try:
        flt = json.loads(r["filters_json"] or "{}")
    except (TypeError, ValueError):
        flt = {}
    return ReportDef(
        def_id=r["def_id"], name=r["name"],
        report_type=r["report_type"],
        description=r["description"],
        filters=flt if isinstance(flt, dict) else {},
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_def(payload: dict[str, Any]) -> ReportDef:
    init_db()
    name = str(_require(payload.get("name"), "Name")).strip()
    rt = _validate_report_type(payload.get("report_type"))
    flt = _normalise_filters(rt, payload.get("filters"))
    desc = (payload.get("description") or "").strip() or None
    by = (payload.get("created_by") or "").strip() or None
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO audit_report_defs
                       (name, report_type, description, filters_json,
                        created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (name, rt, desc, json.dumps(flt), by),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A saved report named {name!r} already exists") from None
    out = get_def(new_id)
    assert out is not None
    logger.info("Created saved audit report #%d (%s)", new_id, name)
    return out


def get_def(def_id: int) -> ReportDef | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM audit_report_defs WHERE def_id = ?",
            (def_id,)).fetchone()
    return _row_def(r) if r else None


def get_def_by_name(name: str) -> ReportDef | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM audit_report_defs WHERE name = ?",
            (name.strip(),)).fetchone()
    return _row_def(r) if r else None


def list_defs(*, report_type: str | None = None) -> list[ReportDef]:
    init_db()
    args: list[Any] = []
    where = ""
    if report_type:
        where = "WHERE report_type = ?"
        args.append(report_type)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_report_defs {where} "
            "ORDER BY LOWER(name)", args).fetchall()
    return [_row_def(r) for r in rows]


def update_def(def_id: int, payload: dict[str, Any]) -> ReportDef:
    init_db()
    existing = get_def(def_id)
    if existing is None:
        raise ValidationError(f"No saved report #{def_id}")
    name = str(payload.get("name", existing.name)).strip()
    if not name:
        raise ValidationError("Name is required")
    rt = _validate_report_type(
        payload.get("report_type", existing.report_type))
    flt_in = payload.get("filters", existing.filters)
    flt = _normalise_filters(rt, flt_in)
    desc_raw = payload.get("description", existing.description)
    desc = (desc_raw or "").strip() or None if isinstance(
        desc_raw, str) else desc_raw
    with _connect() as conn:
        try:
            conn.execute(
                """UPDATE audit_report_defs
                      SET name=?, report_type=?, description=?,
                          filters_json=?, updated_at=datetime('now')
                    WHERE def_id=?""",
                (name, rt, desc, json.dumps(flt), def_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A saved report named {name!r} already exists") from None
    out = get_def(def_id)
    assert out is not None
    logger.info("Updated saved audit report #%d", def_id)
    return out


def delete_def(def_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM audit_report_defs WHERE def_id = ?",
            (def_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted saved audit report #%d", def_id)
        return True
    return False


# ── Builders ──────────────────────────────────────────────────────

def _query_events(filters: dict[str, Any], *,
                  default_limit: int = 5000) -> list[Any]:
    return _af.list_events(
        actor=filters.get("actor"),
        action=filters.get("action"),
        entity_type=filters.get("entity_type"),
        entity_id=filters.get("entity_id"),
        severity=filters.get("severity"),
        source=filters.get("source"),
        summary_like=filters.get("summary_like"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        limit=filters.get("limit", default_limit),
    )


def _build_actions_by_user(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    bucket: dict[str, int] = {}
    last: dict[str, str] = {}
    for e in events:
        a = e.actor or "(system)"
        bucket[a] = bucket.get(a, 0) + 1
        if a not in last or (e.ts or "") > last[a]:
            last[a] = e.ts or ""
    rows = sorted(
        ([a, n, last.get(a, "")] for a, n in bucket.items()),
        key=lambda r: (-int(r[1]), str(r[0]).lower()))
    return ["Actor", "Events", "Most recent"], rows


def _build_actions_by_type(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    bucket: dict[str, int] = {}
    for e in events:
        bucket[e.action] = bucket.get(e.action, 0) + 1
    rows = sorted(
        ([k, v] for k, v in bucket.items()),
        key=lambda r: (-int(r[1]), str(r[0])))
    return ["Action", "Events"], rows


def _build_events_timeline(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    rows: list[list[Any]] = []
    for e in events:
        rows.append([
            e.ts, e.actor or "—", e.action, e.severity, e.source,
            f"{e.entity_type or '—'}#{e.entity_id or '—'}",
            e.summary,
        ])
    return ["When", "Actor", "Action", "Severity", "Source",
            "Entity", "Summary"], rows


def _build_deletes(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    f = dict(filters)
    f["action"] = "delete"
    return _build_events_timeline(f)


def _build_security_events(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    out: list[list[Any]] = []
    for e in events:
        if (e.action in ("login", "logout", "login_failed")
                or e.severity in ("warning", "error")):
            out.append([
                e.ts, e.actor or "—", e.action, e.severity,
                e.source, e.ip_address or "—", e.summary,
            ])
    return ["When", "Actor", "Action", "Severity", "Source",
            "IP", "Summary"], out


def _build_failed_logins(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    f = dict(filters)
    f["action"] = "login_failed"
    events = _query_events(f)
    rows: list[list[Any]] = []
    for e in events:
        rows.append([e.ts, e.actor or "—", e.ip_address or "—",
                     e.source, e.summary])
    return ["When", "Attempted user", "IP", "Source", "Summary"], rows


def _build_severity_breakdown(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    bucket: dict[str, int] = {s: 0 for s in _af.SEVERITIES}
    for e in events:
        bucket[e.severity] = bucket.get(e.severity, 0) + 1
    total = sum(bucket.values()) or 1
    rows: list[list[Any]] = []
    for sev in _af.SEVERITIES:
        n = bucket.get(sev, 0)
        pct = (n / total) * 100
        rows.append([sev, n, f"{pct:.1f}%"])
    return ["Severity", "Events", "% of total"], rows


def _build_daily_summary(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    by_day: dict[str, dict[str, int]] = {}
    for e in events:
        day = (e.ts or "")[:10] or "?"
        d = by_day.setdefault(day, {"total": 0})
        d["total"] += 1
        d[e.severity] = d.get(e.severity, 0) + 1
    rows = []
    for day in sorted(by_day.keys()):
        d = by_day[day]
        rows.append([day, d["total"],
                     d.get("info", 0), d.get("audit", 0),
                     d.get("warning", 0), d.get("error", 0)])
    return ["Day", "Total", "Info", "Audit",
            "Warning", "Error"], rows


def _build_entity_history(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    if not filters.get("entity_id"):
        raise ValidationError("entity_history requires entity_id")
    events = _query_events(filters)
    rows: list[list[Any]] = []
    for e in events:
        rows.append([e.ts, e.actor or "—", e.action,
                     e.severity, e.source, e.summary])
    return ["When", "Actor", "Action", "Severity",
            "Source", "Summary"], rows


def _build_source_breakdown(filters: dict[str, Any]) -> tuple[
        list[str], list[list[Any]]]:
    events = _query_events(filters)
    bucket: dict[str, int] = {s: 0 for s in _af.SOURCES}
    for e in events:
        bucket[e.source] = bucket.get(e.source, 0) + 1
    total = sum(bucket.values()) or 1
    rows: list[list[Any]] = []
    for src in _af.SOURCES:
        n = bucket.get(src, 0)
        pct = (n / total) * 100
        rows.append([src, n, f"{pct:.1f}%"])
    return ["Source", "Events", "% of total"], rows


_BUILDERS: dict[str, Callable[[dict[str, Any]],
                              tuple[list[str], list[list[Any]]]]] = {
    "actions_by_user":    _build_actions_by_user,
    "actions_by_type":    _build_actions_by_type,
    "events_timeline":    _build_events_timeline,
    "deletes":            _build_deletes,
    "security_events":    _build_security_events,
    "failed_logins":      _build_failed_logins,
    "severity_breakdown": _build_severity_breakdown,
    "daily_summary":      _build_daily_summary,
    "entity_history":     _build_entity_history,
    "source_breakdown":   _build_source_breakdown,
}


def run_report(report_type: str, *,
               filters: dict[str, Any] | None = None,
               name: str | None = None) -> ReportResult:
    rt = _validate_report_type(report_type)
    flt = _normalise_filters(rt, filters)
    builder = _BUILDERS[rt]
    headers, rows = builder(flt)
    return ReportResult(
        report_type=rt,
        name=(name or REPORT_LABELS[rt]).strip() or REPORT_LABELS[rt],
        headers=headers, rows=rows, filters=flt,
        generated_at=_now_iso(),
    )


def run_def(def_id: int) -> ReportResult:
    d = get_def(def_id)
    if d is None:
        raise ValidationError(f"No saved report #{def_id}")
    return run_report(d.report_type, filters=d.filters, name=d.name)


# ── Run snapshots ────────────────────────────────────────────────

def save_run(result: ReportResult, *,
             def_id: int | None = None,
             run_by: str | None = None,
             notes: str | None = None) -> "ReportRun":
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO audit_report_runs
                  (def_id, report_type, name, filters_json,
                   headers_json, rows_json, row_count,
                   run_by, run_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
            (def_id, result.report_type, result.name,
             json.dumps(result.filters, default=str),
             json.dumps(result.headers, default=str),
             json.dumps(result.rows, default=str),
             result.row_count,
             (run_by or "").strip() or None,
             (notes or "").strip() or None),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_run(new_id)
    assert out is not None
    logger.info("Saved audit report run #%d (%s, %d row(s))",
                new_id, result.report_type, result.row_count)
    return out


def _row_run(r: sqlite3.Row) -> ReportRun:
    def _load(s: str, default: Any) -> Any:
        try:
            return json.loads(s) if s else default
        except (TypeError, ValueError):
            return default
    return ReportRun(
        run_id=r["run_id"], def_id=r["def_id"],
        report_type=r["report_type"], name=r["name"],
        filters=_load(r["filters_json"], {}),
        headers=_load(r["headers_json"], []),
        rows=_load(r["rows_json"], []),
        row_count=r["row_count"],
        run_by=r["run_by"], run_at=r["run_at"],
        notes=r["notes"],
    )


def get_run(run_id: int) -> ReportRun | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM audit_report_runs WHERE run_id = ?",
            (run_id,)).fetchone()
    return _row_run(r) if r else None


def list_runs(*, report_type: str | None = None,
              def_id: int | None = None,
              limit: int = 200) -> list[ReportRun]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if report_type:
        clauses.append("report_type = ?")
        args.append(report_type)
    if def_id is not None:
        clauses.append("def_id = ?")
        args.append(def_id)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_report_runs {where} "
            f"ORDER BY run_at DESC, run_id DESC LIMIT {int(limit)}",
            args).fetchall()
    return [_row_run(r) for r in rows]


def delete_run(run_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM audit_report_runs WHERE run_id = ?",
            (run_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted audit report run #%d", run_id)
        return True
    return False


# ── Rendering / export ───────────────────────────────────────────

def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def render(result: ReportResult, *,
           fmt: str = DEFAULT_EXPORT_FORMAT) -> str:
    fmt = (fmt or DEFAULT_EXPORT_FORMAT).lower().strip()
    if fmt not in EXPORT_FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(EXPORT_FORMATS)}")
    if fmt in ("csv", "tsv"):
        delim = "," if fmt == "csv" else "\t"
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=delim,
                       quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(result.headers)
        for r in result.rows:
            w.writerow([_stringify(c) for c in r])
        return buf.getvalue()
    if fmt == "json":
        body = {
            "report_type": result.report_type,
            "name": result.name,
            "generated_at": result.generated_at,
            "filters": result.filters,
            "headers": result.headers,
            "rows": result.rows,
        }
        return json.dumps(body, indent=2, default=str,
                          ensure_ascii=False) + "\n"
    if fmt == "markdown":
        lines: list[str] = []
        lines.append(f"# {result.name}")
        lines.append("")
        lines.append(f"_Generated: {result.generated_at}_")
        if result.filters:
            lines.append("")
            lines.append("**Filters:** " + ", ".join(
                f"`{k}={v}`" for k, v in result.filters.items()))
        lines.append("")
        if not result.rows:
            lines.append("_(no rows)_")
            return "\n".join(lines) + "\n"

        def _esc(s: str) -> str:
            return s.replace("|", "\\|").replace("\n", " ⏎ ")
        lines.append("| " + " | ".join(
            _esc(h) for h in result.headers) + " |")
        lines.append("|" + "|".join(
            "---" for _ in result.headers) + "|")
        for r in result.rows:
            lines.append("| " + " | ".join(
                _esc(_stringify(c)) for c in r) + " |")
        return "\n".join(lines) + "\n"
    raise ValidationError(f"Unsupported format: {fmt}")


def export(result: ReportResult, output_path: str | Path, *,
           fmt: str | None = None) -> dict[str, Any]:
    path = Path(output_path).expanduser()
    if fmt is None:
        suffix = path.suffix.lower().lstrip(".")
        fmt = ({"md": "markdown"}.get(suffix, suffix)
               if suffix else DEFAULT_EXPORT_FORMAT)
        if fmt not in EXPORT_FORMATS:
            fmt = DEFAULT_EXPORT_FORMAT
    body = render(result, fmt=fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = path.write_text(body, encoding="utf-8")
    logger.info("Exported audit report %s → %s (%d byte(s), %d row(s))",
                result.report_type, path, written, result.row_count)
    return {
        "path": str(path), "fmt": fmt,
        "row_count": result.row_count,
        "bytes_written": written,
    }


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class AuditOverview:
    total_events: int
    last_24h: int
    last_7d: int
    last_30d: int
    by_severity: dict[str, int]
    by_action_top: list[tuple[str, int]]
    by_actor_top: list[tuple[str, int]]
    failed_logins_24h: int
    deletes_24h: int
    saved_report_count: int
    saved_run_count: int


def overview() -> AuditOverview:
    init_db()
    events = _af.list_events(limit=10000)
    now = _dt.datetime.now()
    cutoffs = {
        "24h": now - _dt.timedelta(hours=24),
        "7d":  now - _dt.timedelta(days=7),
        "30d": now - _dt.timedelta(days=30),
    }

    def _after(ev, cutoff) -> bool:
        try:
            return _dt.datetime.fromisoformat(
                (ev.ts or "").replace("T", " ")[:19]) >= cutoff
        except ValueError:
            return False

    by_sev: dict[str, int] = {s: 0 for s in _af.SEVERITIES}
    by_action: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    fl24 = del24 = c24 = c7 = c30 = 0
    for e in events:
        by_sev[e.severity] = by_sev.get(e.severity, 0) + 1
        by_action[e.action] = by_action.get(e.action, 0) + 1
        a = e.actor or "(system)"
        by_actor[a] = by_actor.get(a, 0) + 1
        if _after(e, cutoffs["24h"]):
            c24 += 1
            if e.action == "login_failed":
                fl24 += 1
            if e.action == "delete":
                del24 += 1
        if _after(e, cutoffs["7d"]):
            c7 += 1
        if _after(e, cutoffs["30d"]):
            c30 += 1

    top_action = sorted(by_action.items(),
                         key=lambda kv: -kv[1])[:10]
    top_actor = sorted(by_actor.items(),
                        key=lambda kv: -kv[1])[:10]
    with _connect() as conn:
        def_n = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_report_defs").fetchone()["n"]
        run_n = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_report_runs").fetchone()["n"]
    return AuditOverview(
        total_events=len(events),
        last_24h=c24, last_7d=c7, last_30d=c30,
        by_severity=by_sev,
        by_action_top=top_action, by_actor_top=top_actor,
        failed_logins_24h=fl24, deletes_24h=del24,
        saved_report_count=def_n, saved_run_count=run_n,
    )
