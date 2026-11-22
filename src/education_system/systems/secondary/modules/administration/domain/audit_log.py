"""One read-only viewer over the Secondary School's audit trails.

Two kinds of trail are read:

* the **activity log** (:mod:`infrastructure.logging.activity_log`): one line per
  action - who, role, interface, action, target, outcome and details - in
  the log file and its rotated copies (``activity.log.1`` ... ``.10``);
* every **``*_audit`` table** in the school database (``pupil_audit``,
  ``exclusion_audit``, ``settings_audit``...). They are found in
  ``sqlite_master`` each time, so a new module's trail appears without a
  change here. Their columns differ a little, so each is read through what
  it has: the time (``at``), the person (``actor``), the action, the record
  it is about (``pupil_id`` or the table's own ``*_id``) and the rest as
  detail.

Filters: date range, user, action (or a prefix such as ``exclusions.``),
area (the action's first part) or table, target id and outcome; results are
newest first, in pages. Plus a detail view, CSV export (cells made safe for
spreadsheets), counts by user and by action, and the refused / failed
actions (outcome ``denied``, ``invalid`` ...).

Kept from the old Audit Reports: the ten canned reports (actions by user,
by type, timeline, deletions, security events, failed logins, outcome
breakdown, daily summary, entity history, source breakdown), saved report
definitions (new, edit, run, delete) and frozen snapshots of runs (save,
view, delete), and the overview.

Read-only over the trails: nothing here changes or deletes an audit row or
a log line. Admin only (``access.RESTRICTED["Audit Log"]``), and every read
is itself written to the activity log.

Times: the activity log is written in local time and the tables in UTC
(``datetime('now')``); table times are shown in local time so the two sort
together.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from education_system.systems.secondary.core.exceptions import errors
from education_system.systems.secondary.core.permissions.access import RESTRICTED, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = errors.ValidationError
PermissionDenied = errors.PermissionDenied
NotFound = errors.NotFound

LABEL = "Audit Log"
ACTIVITY = "activity log"
#: Outcomes that mean the action did not happen as asked.
FAILED_OUTCOMES = frozenset({"denied", "invalid", "failed", "error", "not_found",
                             "possible_duplicate", "not_built"})
PAGE_SIZE = 100
_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_TIME_COLS = ("at", "created_at", "changed_at", "timestamp", "logged_at")
_ACTOR_COLS = ("actor", "changed_by", "username", "user", "performed_by", "created_by")
_ACTION_COLS = ("action", "event", "change_type")
_DETAIL_COLS = ("detail", "details", "fields", "changes", "notes")

REPORT_TYPES: tuple[str, ...] = (
    "actions_by_user", "actions_by_type", "events_timeline", "deletes", "security_events",
    "failed_logins", "severity_breakdown", "daily_summary", "entity_history",
    "source_breakdown")
REPORT_LABELS: dict[str, str] = {
    "actions_by_user": "Actions by user", "actions_by_type": "Actions by action type",
    "events_timeline": "Events timeline", "deletes": "Deletions",
    "security_events": "Security events", "failed_logins": "Failed logins",
    "severity_breakdown": "Outcome breakdown", "daily_summary": "Daily summary",
    "entity_history": "Entity history", "source_breakdown": "Source breakdown"}
REPORT_DESCRIPTIONS: dict[str, str] = {
    "actions_by_user": "Count of events by person over a date window.",
    "actions_by_type": "Count of events grouped by action.",
    "events_timeline": "Flat list of events for the chosen window/filter.",
    "deletes": "Every delete recorded in the period - for incident reviews.",
    "security_events": "Sign-ins, sign-outs, refused screens and any refused or failed "
                       "action.",
    "failed_logins": "Sign-in and session events that did not succeed.",
    "severity_breakdown": "Count of events by outcome (ok, denied, invalid...).",
    "daily_summary": "Events per day, with people and refusals.",
    "entity_history": "Everything recorded about one record (give a target id).",
    "source_breakdown": "Count of events by trail (activity log and each audit table)."}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log_reports (
    report_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    report_type  TEXT NOT NULL,
    description  TEXT,
    filters      TEXT NOT NULL DEFAULT '{}',
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audit_log_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type  TEXT NOT NULL,
    title        TEXT NOT NULL,
    filters      TEXT NOT NULL DEFAULT '{}',
    columns      TEXT NOT NULL,
    rows         TEXT NOT NULL,
    row_count    INTEGER NOT NULL,
    run_by       TEXT,
    run_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("audit_log", _SCHEMA)


@dataclass(frozen=True)
class Entry:
    source: str                 # "activity log" or the table name
    at: str                     # local time, YYYY-MM-DD HH:MM:SS
    user: str
    action: str
    target: str
    outcome: str = "ok"
    role: str = ""
    interface: str = ""
    session: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    row_id: int | None = None   # the audit row (tables) or line number (log)

    @property
    def area(self) -> str:
        """The action's first part (``exclusions.create`` -> ``exclusions``),
        or the table name for a table row."""
        if self.source != ACTIVITY:
            return self.source
        return self.action.split(".", 1)[0]

    @property
    def failed(self) -> bool:
        return self.outcome in FAILED_OUTCOMES

    @property
    def key(self) -> str:
        return f"{self.source}#{self.row_id}"

    def detail_text(self) -> str:
        return ", ".join(f"{k}={_short(v)}" for k, v in self.detail.items())


def _short(v: Any) -> str:
    text = v if isinstance(v, str) else json.dumps(v, default=str)
    return text if len(text) <= 120 else text[:117] + "..."


@dataclass(frozen=True)
class Filters:
    date_from: str | None = None
    date_to: str | None = None
    user: str | None = None
    action: str | None = None   # exact action, or a prefix ending in "." or "*"
    area: str | None = None     # action area, or a table name, or "activity log"
    target: str | None = None
    outcome: str | None = None  # "failed" = any of FAILED_OUTCOMES
    text: str | None = None     # anywhere in the detail

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "")}


@dataclass
class Page:
    entries: list[Entry]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


@dataclass
class ReportResult:
    report_type: str
    title: str
    columns: list[str]
    rows: list[list[Any]]
    filters: dict[str, Any]
    generated_at: str


# ── Who may read ─────────────────────────────────────────────────────

def can_read(actor: Principal) -> bool:
    return actor.role in RESTRICTED.get(LABEL, frozenset({"admin", "superadmin"}))


def _require(actor: Principal, action: str) -> None:
    if not can_read(actor):
        activity_log.record(f"audit_log.{action}", outcome="denied", principal=actor)
        raise PermissionDenied("Only a system administrator can read the audit log.")


# ── Cleaning filters ─────────────────────────────────────────────────

def clean_filters(data: Filters | dict[str, Any] | None) -> Filters:
    if isinstance(data, Filters):
        data = data.__dict__
    data = dict(data or {})
    problems = []
    out: dict[str, Any] = {}
    for key in ("date_from", "date_to"):
        v = str(data.get(key) or "").strip()
        if v:
            try:
                v = _dt.date.fromisoformat(v).isoformat()
            except ValueError:
                problems.append(f"{'From' if key == 'date_from' else 'To'} must be a date "
                                "(YYYY-MM-DD)")
                v = ""
        out[key] = v or None
    if out["date_from"] and out["date_to"] and out["date_to"] < out["date_from"]:
        problems.append("The To date is before the From date")
    for key in ("user", "action", "area", "target", "outcome", "text"):
        v = " ".join(str(data.get(key) or "").split())[:100]
        out[key] = v or None
    if problems:
        raise ValidationError(problems)
    return Filters(**out)


# ── The activity log ─────────────────────────────────────────────────

def log_files() -> list[Path]:
    """The activity log and its rotated copies, oldest first."""
    base = activity_log.log_path()
    rotated = sorted((p for p in base.parent.glob(base.name + ".*")
                      if p.suffix[1:].isdigit()), key=lambda p: -int(p.suffix[1:]))
    return [p for p in rotated + [base] if p.is_file()]


def parse_line(line: str, n: int = 0) -> Entry | None:
    """One activity line (see activity_log's format), or None if it isn't one."""
    parts = [p.strip() for p in line.rstrip("\n").split(" | ")]
    if len(parts) < 8 or not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", parts[0]):
        return None
    kv: dict[str, str] = {}
    fixed = {"session": "", "user": "", "role": ""}
    for p in parts[1:4]:
        k, _, v = p.partition("=")
        fixed[k] = v
    interface, action = parts[4], parts[5]
    for p in parts[6:]:
        k, sep, v = p.partition("=")
        if sep:
            kv[k] = v
    target = kv.pop("target", "-")
    outcome = kv.pop("outcome", "ok")
    return Entry(ACTIVITY, parts[0], "" if fixed["user"] == "-" else fixed["user"], action,
                 "" if target == "-" else target, outcome,
                 "" if fixed["role"] == "-" else fixed["role"],
                 "" if interface == "-" else interface,
                 "" if fixed["session"] == "-" else fixed["session"], kv, n)


def _activity_entries(f: Filters) -> list[Entry]:
    out = []
    n = 0
    for path in log_files():
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                n += 1
                e = parse_line(line, n)
                if e is not None and _matches(e, f):
                    out.append(e)
    return out


# ── The *_audit tables ───────────────────────────────────────────────

def audit_tables() -> list[str]:
    """Every ``*_audit`` table in the school database, by name."""
    with database.connect() as conn:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE '%\\_audit' "
            "ESCAPE '\\' ORDER BY name")]
    return [n for n in names if _NAME_RE.match(n)]


def sources() -> list[str]:
    return [ACTIVITY, *audit_tables()]


def _shape(conn, table: str) -> dict[str, Any]:
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]  # nosec B608 - name from sqlite_master, checked
    pk = next((c for c in cols if c in ("audit_id", "id", "log_id")), "rowid")
    ids = [c for c in cols if c.endswith("_id") and c != pk]
    target = "pupil_id" if "pupil_id" in ids else (ids[0] if ids else
                                                    ("key" if "key" in cols else None))
    return {"cols": cols, "pk": pk,
            "time": next((c for c in _TIME_COLS if c in cols), None),
            "actor": next((c for c in _ACTOR_COLS if c in cols), None),
            "action": next((c for c in _ACTION_COLS if c in cols), None),
            "target": target, "ids": ids}


def _to_local(utc_text: str | None) -> str:
    if not utc_text:
        return ""
    try:
        d = _dt.datetime.fromisoformat(str(utc_text)[:19].replace("T", " "))
    except ValueError:
        return str(utc_text)
    if len(str(utc_text)) <= 10:
        return d.strftime("%Y-%m-%d %H:%M:%S")
    return d.replace(tzinfo=_dt.UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _table_entries(table: str, f: Filters) -> list[Entry]:
    with database.connect() as conn:
        s = _shape(conn, table)
        where, params = [], []
        if s["time"] and f.date_from:      # a day either side: the times are UTC
            where.append(f'"{s["time"]}" >= ?')
            params.append((_dt.date.fromisoformat(f.date_from) - _dt.timedelta(days=1))
                          .isoformat())
        if s["time"] and f.date_to:
            where.append(f'"{s["time"]}" < ?')
            params.append((_dt.date.fromisoformat(f.date_to) + _dt.timedelta(days=2))
                          .isoformat())
        if f.user:
            if not s["actor"]:
                return []
            where.append(f'lower("{s["actor"]}") = lower(?)')
            params.append(f.user)
        if f.target:
            cols = [c for c in (*s["ids"], s["target"]) if c]
            if not cols:
                return []
            where.append("(" + " OR ".join(f'CAST("{c}" AS TEXT) = ?' for c in cols) + ")")
            params += [f.target] * len(cols)
        sql = f'SELECT {"rowid AS _rid, " if s["pk"] == "rowid" else ""}* FROM "{table}"'  # nosec B608 - checked name
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = conn.execute(sql, params).fetchall()
    out = []
    skip = {s["pk"], s["time"], s["actor"], s["action"], "_rid"}
    for r in rows:
        d = dict(r)
        detail: dict[str, Any] = {}
        for c in s["cols"]:
            if c in skip or d.get(c) in (None, ""):
                continue
            v = d[c]
            if isinstance(v, str) and v[:1] in ('{', '[', '"'):
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            if c in _DETAIL_COLS and isinstance(v, dict):
                detail.update(v)
            else:
                detail[c] = v
        e = Entry(table, _to_local(d.get(s["time"])) if s["time"] else "",
                  str(d.get(s["actor"]) or "") if s["actor"] else "",
                  str(d.get(s["action"]) or "") if s["action"] else "",
                  str(d.get(s["target"]) if s["target"] and d.get(s["target"]) is not None
                      else ""),
                  "ok", detail=detail,
                  row_id=d.get("_rid") if s["pk"] == "rowid" else d.get(s["pk"]))
        if _matches(e, f):
            out.append(e)
    return out


# ── Matching and searching ───────────────────────────────────────────

def _matches(e: Entry, f: Filters) -> bool:
    day = e.at[:10]
    if f.date_from and (not day or day < f.date_from):
        return False
    if f.date_to and (not day or day > f.date_to):
        return False
    if f.user and e.user.lower() != f.user.lower():
        return False
    if f.action:
        a = f.action.lower()
        if a.endswith("*"):
            if not e.action.lower().startswith(a[:-1]):
                return False
        elif a.endswith("."):
            if not e.action.lower().startswith(a):
                return False
        elif e.action.lower() != a:
            return False
    if f.area and f.area.lower() not in (e.area.lower(), e.source.lower()):
        return False
    if f.target and e.source == ACTIVITY and e.target.lower() != f.target.lower() \
            and str(e.detail.get("case") or e.detail.get("id") or "") != f.target:
        return False
    if f.outcome:
        o = f.outcome.lower()
        if o == "failed":
            if not e.failed:
                return False
        elif e.outcome.lower() != o:
            return False
    if f.text and f.text.lower() not in json.dumps(e.detail, default=str).lower() \
            and f.text.lower() not in e.target.lower():
        return False
    return True


def _collect(f: Filters, only: Iterable[str] | None = None) -> list[Entry]:
    wanted = set(only) if only else None
    entries: list[Entry] = []
    area = (f.area or "").lower()
    tables = audit_tables()
    if (wanted is None or ACTIVITY in wanted) and area not in tables:
        entries += _activity_entries(f)
    if f.outcome and f.outcome.lower() != "ok":
        tables = []          # table rows record things that happened
    for t in tables:
        if wanted is not None and t not in wanted:
            continue
        if area and area not in (t, ACTIVITY) and not t.startswith(area):
            continue
        if area == ACTIVITY:
            continue
        entries += _table_entries(t, Filters(**{**f.__dict__, "area": None}))
    entries.sort(key=lambda e: (e.at, e.source, e.row_id or 0), reverse=True)
    return entries


def search(filters: Filters | dict[str, Any] | None = None, *, actor: Principal,
           page: int = 1, page_size: int = PAGE_SIZE) -> Page:
    """Newest first, one page at a time."""
    _require(actor, "search")
    f = clean_filters(filters)
    rows = _collect(f)
    size = max(1, min(int(page_size), 1000))
    page = max(1, int(page))
    activity_log.record("audit_log.search", principal=actor, page=page, matched=len(rows),
                        filters=",".join(sorted(f.as_dict())) or None)
    return Page(rows[(page - 1) * size: page * size], len(rows), page, size)


def failures(filters: Filters | dict[str, Any] | None = None, *, actor: Principal,
             page: int = 1, page_size: int = PAGE_SIZE) -> Page:
    """Refused and failed actions only."""
    f = clean_filters(filters)
    return search(Filters(**{**f.__dict__, "outcome": f.outcome or "failed"}), actor=actor,
                  page=page, page_size=page_size)


def get_entry(source: str, row_id: int, *, actor: Principal) -> Entry:
    """One entry in full (the detail view)."""
    _require(actor, "detail")
    if source == ACTIVITY:
        rows = [e for e in _activity_entries(Filters()) if e.row_id == int(row_id)]
    else:
        if source not in audit_tables():
            raise NotFound(f"No audit trail {source}")
        rows = [e for e in _table_entries(source, Filters()) if e.row_id == int(row_id)]
    if not rows:
        raise NotFound(f"No entry {row_id} in {source}")
    activity_log.record("audit_log.detail", target=f"{source}#{row_id}", principal=actor)
    return rows[0]


def summary(filters: Filters | dict[str, Any] | None = None, *, actor: Principal
            ) -> dict[str, Any]:
    """Counts by user, by action, by area and by outcome."""
    _require(actor, "summary")
    f = clean_filters(filters)
    rows = _collect(f)
    activity_log.record("audit_log.summary", principal=actor, matched=len(rows))
    return {"total": len(rows), "failed": sum(e.failed for e in rows),
            "users": len({e.user for e in rows if e.user}),
            "by_user": Counter(e.user or "(none)" for e in rows).most_common(),
            "by_action": Counter(e.action or "(none)" for e in rows).most_common(),
            "by_area": Counter(e.area for e in rows).most_common(),
            "by_outcome": Counter(e.outcome for e in rows).most_common(),
            "first": rows[-1].at if rows else None, "last": rows[0].at if rows else None}


def users() -> list[str]:
    """Everyone who appears in a trail (for the user filter)."""
    names = {e.user for e in _activity_entries(Filters()) if e.user}
    with database.connect() as conn:
        for t in audit_tables():
            s = _shape(conn, t)
            if s["actor"]:
                names |= {r[0] for r in conn.execute(
                    f'SELECT DISTINCT "{s["actor"]}" FROM "{t}"') if r[0]}  # nosec B608
    return sorted(names, key=str.lower)


def areas() -> list[str]:
    """Action areas seen in the activity log, then the tables."""
    seen = sorted({e.area for e in _activity_entries(Filters()) if e.area})
    return [ACTIVITY, *seen, *audit_tables()]


# ── Export ───────────────────────────────────────────────────────────

CSV_COLUMNS = ["time", "source", "user", "role", "interface", "action", "target", "outcome",
               "session", "detail"]


def export_csv(path: str | Path, filters: Filters | dict[str, Any] | None = None, *,
               actor: Principal) -> int:
    _require(actor, "export")
    f = clean_filters(filters)
    rows = _collect(f)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_COLUMNS)
        for e in rows:
            w.writerow([e.at, e.source, _safe(e.user), e.role, e.interface, _safe(e.action),
                        _safe(e.target), e.outcome, e.session,
                        _safe(json.dumps(e.detail, default=str, sort_keys=True))])
    activity_log.record("audit_log.export", principal=actor, rows=len(rows),
                        filters=",".join(sorted(f.as_dict())) or None)
    return len(rows)


# ── Canned reports (kept from the old Audit Reports) ─────────────────

def _counts(rows: list[Entry], key) -> list[list[Any]]:
    by: dict[str, list[Entry]] = {}
    for e in rows:
        by.setdefault(key(e), []).append(e)
    return [[k, len(v), sum(x.failed for x in v), max(x.at for x in v)]
            for k, v in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))]


def _timeline(rows: list[Entry]) -> list[list[Any]]:
    return [[e.at, e.source, e.user, e.action, e.target, e.outcome, e.detail_text()]
            for e in rows]


_TIMELINE_COLS = ["Time", "Source", "User", "Action", "Target", "Outcome", "Detail"]


def run_report(report_type: str, filters: Filters | dict[str, Any] | None = None, *,
               actor: Principal) -> ReportResult:
    _require(actor, "report")
    if report_type not in REPORT_TYPES:
        raise ValidationError([f"Report must be one of {', '.join(REPORT_TYPES)}"])
    f = clean_filters(filters)
    if report_type == "entity_history" and not f.target:
        raise ValidationError(["Entity history needs a target id (admission number, record "
                               "id or setting key)"])
    rows = _collect(f)
    cols: list[str]
    if report_type == "actions_by_user":
        cols, out = ["User", "Events", "Refused/failed", "Latest"], _counts(
            rows, lambda e: e.user or "(none)")
    elif report_type == "actions_by_type":
        cols, out = ["Action", "Events", "Refused/failed", "Latest"], _counts(
            rows, lambda e: e.action or "(none)")
    elif report_type == "severity_breakdown":
        cols, out = ["Outcome", "Events", "Refused/failed", "Latest"], _counts(
            rows, lambda e: e.outcome)
    elif report_type == "source_breakdown":
        cols, out = ["Trail", "Events", "Refused/failed", "Latest"], _counts(
            rows, lambda e: e.source)
    elif report_type == "daily_summary":
        cols = ["Day", "Events", "People", "Refused/failed"]
        days: dict[str, list[Entry]] = {}
        for e in rows:
            days.setdefault(e.at[:10] or "(no date)", []).append(e)
        out = [[d, len(v), len({x.user for x in v if x.user}), sum(x.failed for x in v)]
               for d, v in sorted(days.items(), reverse=True)]
    else:
        pick = {
            "events_timeline": lambda e: True,
            "entity_history": lambda e: True,
            "deletes": lambda e: "delete" in e.action.lower() or "remove" in e.action.lower(),
            "security_events": lambda e: e.action.startswith(("session.", "login", "auth",
                                                              "menu.open", "audit_log."))
            and (e.failed or e.action.startswith(("session.", "login", "auth"))) or
            e.outcome == "denied",
            "failed_logins": lambda e: e.action.startswith(("session.", "login", "auth",
                                                            "sign")) and e.failed,
        }[report_type]
        cols, out = _TIMELINE_COLS, _timeline([e for e in rows if pick(e)])
    activity_log.record("audit_log.report", target=report_type, principal=actor,
                        rows=len(out))
    return ReportResult(report_type, REPORT_LABELS[report_type], cols, out, f.as_dict(),
                        _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def render(result: ReportResult) -> str:
    """A report as plain text."""
    lines = [f"{result.title}  ({result.generated_at})"]
    if result.filters:
        lines.append("Filters: " + ", ".join(f"{k}={v}" for k, v in result.filters.items()))
    widths = [min(40, max([len(c)] + [len(str(r[i])) for r in result.rows]))
              for i, c in enumerate(result.columns)]
    lines.append("  ".join(c.ljust(w) for c, w in zip(result.columns, widths)))
    lines.append("  ".join("-" * w for w in widths))
    for r in result.rows:
        lines.append("  ".join(str(v)[:w].ljust(w) for v, w in zip(r, widths)))
    lines.append(f"{len(result.rows)} row(s)")
    return "\n".join(lines)


def export_report(result: ReportResult, path: str | Path, *, actor: Principal) -> int:
    """A report as CSV (or text, for a .txt path)."""
    _require(actor, "export")
    p = Path(path)
    if p.suffix.lower() == ".txt":
        p.write_text(render(result) + "\n", encoding="utf-8")
    else:
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(result.columns)
            w.writerows([[_safe(v) for v in r] for r in result.rows])
    activity_log.record("audit_log.export", target=result.report_type, principal=actor,
                        rows=len(result.rows))
    return len(result.rows)


# ── Saved report definitions ─────────────────────────────────────────

@dataclass(frozen=True)
class ReportDef:
    report_id: int
    name: str
    report_type: str
    description: str | None
    filters: dict[str, Any]
    created_by: str | None
    created_at: str
    updated_at: str


def _def(r) -> ReportDef:
    return ReportDef(r["report_id"], r["name"], r["report_type"], r["description"],
                     json.loads(r["filters"] or "{}"), r["created_by"], r["created_at"],
                     r["updated_at"])


def _clean_def(data: dict[str, Any]) -> dict[str, Any]:
    problems = []
    name = " ".join(str(data.get("name") or "").split())[:80]
    if not name:
        problems.append("Name is required")
    rtype = str(data.get("report_type") or "").strip()
    rtype = next((k for k, v in REPORT_LABELS.items() if rtype in (k, v)), rtype)
    if rtype not in REPORT_TYPES:
        problems.append("Choose a report type")
    try:
        f = clean_filters(data.get("filters") or {}).as_dict()
    except ValidationError as e:
        problems += e.problems
        f = {}
    if problems:
        raise ValidationError(problems)
    return {"name": name, "report_type": rtype, "filters": f,
            "description": (str(data.get("description") or "").strip()[:500] or None)}


def create_def(data: dict[str, Any], *, actor: Principal) -> ReportDef:
    _require(actor, "report_save")
    c = _clean_def(data)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM audit_log_reports WHERE name = ?",
                        (c["name"],)).fetchone():
            raise ValidationError([f"A saved report called {c['name']} already exists"])
        rid = conn.execute(
            "INSERT INTO audit_log_reports (name, report_type, description, filters, "
            "created_by) VALUES (?, ?, ?, ?, ?)",
            (c["name"], c["report_type"], c["description"], json.dumps(c["filters"]),
             actor.username)).lastrowid
    activity_log.record("audit_log.report_save", target=rid, principal=actor)
    return get_def(rid)


def get_def(report_id: int) -> ReportDef:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM audit_log_reports WHERE report_id = ?",
                         (int(report_id),)).fetchone()
    if r is None:
        raise NotFound(f"No saved report #{report_id}")
    return _def(r)


def list_defs(*, actor: Principal) -> list[ReportDef]:
    _require(actor, "report_list")
    with database.connect() as conn:
        return [_def(r) for r in conn.execute(
            "SELECT * FROM audit_log_reports ORDER BY name COLLATE NOCASE")]


def update_def(report_id: int, data: dict[str, Any], *, actor: Principal) -> ReportDef:
    _require(actor, "report_save")
    cur = get_def(report_id)
    c = _clean_def({"name": cur.name, "report_type": cur.report_type,
                    "description": cur.description, "filters": cur.filters, **data})
    with database.connect() as conn:
        clash = conn.execute("SELECT report_id FROM audit_log_reports WHERE name = ? AND "
                             "report_id != ?", (c["name"], cur.report_id)).fetchone()
        if clash:
            raise ValidationError([f"A saved report called {c['name']} already exists"])
        conn.execute("UPDATE audit_log_reports SET name = ?, report_type = ?, description = ?, "
                     "filters = ?, updated_at = datetime('now') WHERE report_id = ?",
                     (c["name"], c["report_type"], c["description"], json.dumps(c["filters"]),
                      cur.report_id))
    activity_log.record("audit_log.report_save", target=cur.report_id, principal=actor)
    return get_def(cur.report_id)


def delete_def(report_id: int, *, actor: Principal) -> bool:
    _require(actor, "report_delete")
    cur = get_def(report_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM audit_log_reports WHERE report_id = ?", (cur.report_id,))
    activity_log.record("audit_log.report_delete", target=cur.report_id, principal=actor)
    return True


def run_def(report_id: int, *, actor: Principal) -> ReportResult:
    d = get_def(report_id)
    res = run_report(d.report_type, d.filters, actor=actor)
    res.title = f"{d.name} ({REPORT_LABELS[d.report_type]})"
    return res


# ── Snapshots of runs ────────────────────────────────────────────────

@dataclass(frozen=True)
class Run:
    run_id: int
    report_type: str
    title: str
    filters: dict[str, Any]
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    run_by: str | None
    run_at: str

    def as_result(self) -> ReportResult:
        return ReportResult(self.report_type, self.title, self.columns, self.rows,
                            self.filters, self.run_at)


def _run(r) -> Run:
    return Run(r["run_id"], r["report_type"], r["title"], json.loads(r["filters"] or "{}"),
               json.loads(r["columns"]), json.loads(r["rows"]), r["row_count"], r["run_by"],
               r["run_at"])


def save_run(result: ReportResult, *, actor: Principal) -> Run:
    """Freeze a result so the same numbers can be shown again later."""
    _require(actor, "snapshot")
    with database.connect() as conn:
        rid = conn.execute(
            "INSERT INTO audit_log_runs (report_type, title, filters, columns, rows, row_count, "
            "run_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (result.report_type, result.title, json.dumps(result.filters),
             json.dumps(result.columns), json.dumps(result.rows, default=str),
             len(result.rows), actor.username)).lastrowid
    activity_log.record("audit_log.snapshot", target=rid, principal=actor)
    return get_run(rid, actor=actor)


def get_run(run_id: int, *, actor: Principal) -> Run:
    _require(actor, "snapshot_view")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM audit_log_runs WHERE run_id = ?",
                         (int(run_id),)).fetchone()
    if r is None:
        raise NotFound(f"No saved run #{run_id}")
    return _run(r)


def list_runs(*, actor: Principal, report_type: str | None = None, limit: int = 200
              ) -> list[Run]:
    _require(actor, "snapshot_list")
    sql, params = "SELECT * FROM audit_log_runs", []
    if report_type:
        sql += " WHERE report_type = ?"
        params.append(report_type)
    with database.connect() as conn:
        return [_run(r) for r in conn.execute(sql + " ORDER BY run_id DESC LIMIT ?",
                                               (*params, int(limit)))]


def delete_run(run_id: int, *, actor: Principal) -> bool:
    _require(actor, "snapshot_delete")
    get_run(run_id, actor=actor)
    with database.connect() as conn:
        conn.execute("DELETE FROM audit_log_runs WHERE run_id = ?", (int(run_id),))
    activity_log.record("audit_log.snapshot_delete", target=run_id, principal=actor)
    return True


# ── Overview ─────────────────────────────────────────────────────────

def overview(*, actor: Principal, days: int = 7) -> dict[str, Any]:
    """The old Overview: the last *days* days at a glance, and every trail."""
    _require(actor, "overview")
    since = (_dt.date.today() - _dt.timedelta(days=max(1, int(days)) - 1)).isoformat()
    rows = _collect(Filters(date_from=since))
    with database.connect() as conn:
        trails = [(t, conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])  # nosec B608
                  for t in audit_tables()]
    files = log_files()
    activity_log.record("audit_log.overview", principal=actor)
    return {"since": since, "events": len(rows), "failed": sum(e.failed for e in rows),
            "users": len({e.user for e in rows if e.user}),
            "top_users": Counter(e.user for e in rows if e.user).most_common(5),
            "top_actions": Counter(e.action for e in rows if e.action).most_common(5),
            "trails": trails, "log_files": [str(p) for p in files],
            "log_bytes": sum(p.stat().st_size for p in files)}
