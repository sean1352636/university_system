"""Activity Feed — system-wide event log for the Secondary School System.

One row per noteworthy user action: logins, CRUD ops on any domain
record, status changes (absence requests approved, accommodations set,
etc.), and admin events. Other modules call ``log(...)`` to drop an
event onto the feed; the views/CLI here read/filter it.

The feed is append-only by default. ``delete_event`` and ``purge`` are
available for admin cleanup (e.g. trimming old data) but should be
used sparingly — this table is primarily an audit trail.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.secondary.infrastructure import paths
from education_system.systems.secondary.domain.operations.communications.activity_feed import (
    activity_feed as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ACTIVITY_FEED_DB

# Coarse-grained action verbs. Free text is allowed too; the enum
# exists to keep filter UIs consistent.
ACTIONS: tuple[str, ...] = (
    "create", "update", "delete",
    "login", "logout", "login_failed",
    "approve", "deny", "withdraw", "cancel",
    "status_change", "review",
    "import", "export", "print",
    "system",
)

# Severity buckets. "audit" is the default for routine CRUD; "warning"
# and "error" are for things that should bubble up in a dashboard tile;
# "info" is low-noise.
SEVERITIES: tuple[str, ...] = ("info", "audit", "warning", "error")
DEFAULT_SEVERITY: str = "audit"

SOURCES: tuple[str, ...] = ("cli", "gui", "api", "system", "background")
DEFAULT_SOURCE: str = "system"

# Known entity types — kept open. Domain modules can pass anything.
KNOWN_ENTITY_TYPES: tuple[str, ...] = (
    "student", "staff", "course", "subject", "class_group",
    "timetable", "attendance", "homework", "gradebook",
    "behaviour", "safeguarding", "wellbeing",
    "absence_request", "academic_year", "academic_term",
    "academic_break", "accessibility_profile",
    "accommodation", "user", "session",
)

_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?Z?)?$"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    actor         TEXT,
    actor_role    TEXT,
    action        TEXT NOT NULL,
    entity_type   TEXT,
    entity_id     TEXT,
    summary       TEXT NOT NULL,
    severity      TEXT NOT NULL DEFAULT 'audit',
    source        TEXT NOT NULL DEFAULT 'system',
    metadata      TEXT,
    ip_address    TEXT
);

CREATE INDEX IF NOT EXISTS idx_af_ts        ON activity_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_af_actor     ON activity_events(actor);
CREATE INDEX IF NOT EXISTS idx_af_action    ON activity_events(action);
CREATE INDEX IF NOT EXISTS idx_af_entity    ON activity_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_af_severity  ON activity_events(severity);
"""


@dataclass
class Event:
    event_id: int
    ts: str
    actor: str | None
    actor_role: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    summary: str
    severity: str
    source: str
    metadata: str | None
    ip_address: str | None

    @property
    def metadata_dict(self) -> dict | None:
        if not self.metadata:
            return None
        try:
            return json.loads(self.metadata)
        except (TypeError, ValueError):
            return None


@dataclass
class Summary:
    total: int
    by_action: dict[str, int]
    by_severity: dict[str, int]
    by_source: dict[str, int]
    by_actor: dict[str, int]            # top 10 actors
    by_entity_type: dict[str, int]
    last_24h: int
    last_7d: int
    last_30d: int
    most_recent_ts: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Activity-feed schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], ts=r["ts"],
        actor=r["actor"], actor_role=r["actor_role"],
        action=r["action"], entity_type=r["entity_type"],
        entity_id=r["entity_id"], summary=r["summary"],
        severity=r["severity"], source=r["source"],
        metadata=r["metadata"], ip_address=r["ip_address"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _validate_ts(value: Any) -> str:
    if value in (None, ""):
        return _now_iso()
    s = str(value).strip()
    if not _TIMESTAMP_RE.match(s):
        raise ValidationError(
            "Timestamp must be ISO-8601 (YYYY-MM-DD[ HH:MM[:SS]])")
    return s


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["ts"] = _validate_ts(payload.get("ts"))

    action = _require(payload.get("action"), "Action").strip()
    out["action"] = action

    severity = (payload.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of: {', '.join(SEVERITIES)}")
    out["severity"] = severity

    source = (payload.get("source") or DEFAULT_SOURCE).strip()
    if source not in SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(SOURCES)}")
    out["source"] = source

    out["summary"] = _require(payload.get("summary"), "Summary").strip()
    out["actor"]        = (payload.get("actor") or "").strip() or None
    out["actor_role"]   = (payload.get("actor_role") or "").strip() or None
    out["entity_type"]  = (payload.get("entity_type") or "").strip() or None
    out["entity_id"]    = (str(payload.get("entity_id") or "").strip()
                            or None)
    out["ip_address"]   = (payload.get("ip_address") or "").strip() or None

    meta = payload.get("metadata")
    if meta is None or meta == "":
        out["metadata"] = None
    elif isinstance(meta, str):
        # Accept already-serialised JSON or plain text — validate
        # JSON if it looks like one.
        s = meta.strip()
        if s.startswith(("{", "[")):
            try:
                json.loads(s)
            except ValueError as e:
                raise ValidationError(
                    f"metadata is not valid JSON: {e}") from None
        out["metadata"] = s
    else:
        try:
            out["metadata"] = json.dumps(meta, default=str)
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"metadata is not JSON-serialisable: {e}") from None

    return out


# ── Logging API ────────────────────────────────────────────────────

def log(
    action: str,
    summary: str,
    *,
    actor: str | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    severity: str = DEFAULT_SEVERITY,
    source: str = DEFAULT_SOURCE,
    metadata: dict | str | None = None,
    ip_address: str | None = None,
    ts: str | None = None,
) -> Event:
    """Append an event to the feed. Returns the created Event.

    Intended to be called from other modules — failure here should not
    take down the caller, so callers may wrap in try/except if they
    want truly best-effort logging.
    """
    return create_event({
        "ts": ts, "action": action, "summary": summary,
        "actor": actor, "actor_role": actor_role,
        "entity_type": entity_type, "entity_id": entity_id,
        "severity": severity, "source": source,
        "metadata": metadata, "ip_address": ip_address,
    })


def create_event(payload: dict[str, Any]) -> Event:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO activity_events
                   (ts, actor, actor_role, action, entity_type, entity_id,
                    summary, severity, source, metadata, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["ts"], p["actor"], p["actor_role"], p["action"],
             p["entity_type"], p["entity_id"], p["summary"],
             p["severity"], p["source"], p["metadata"],
             p["ip_address"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_event(new_id)
    assert out is not None
    logger.debug("Activity log #%d %s %s by %s",
                  new_id, p["action"], p["summary"], p["actor"])
    return out


def get_event(event_id: int) -> Event | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM activity_events WHERE event_id = ?",
            (event_id,)).fetchone()
        return _row(r) if r else None


def list_events(
    *,
    actor: str | None = None,
    actor_role: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    summary_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> list[Event]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if actor:
        clauses.append("actor = ?")
        args.append(actor.strip())
    if actor_role:
        clauses.append("actor_role = ?")
        args.append(actor_role.strip())
    if action:
        clauses.append("action = ?")
        args.append(action.strip())
    if entity_type:
        clauses.append("entity_type = ?")
        args.append(entity_type.strip())
    if entity_id:
        clauses.append("entity_id = ?")
        args.append(str(entity_id).strip())
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    if source:
        if source not in SOURCES:
            raise ValidationError(
                f"Source must be one of: {', '.join(SOURCES)}")
        clauses.append("source = ?")
        args.append(source)
    if summary_like:
        clauses.append("summary LIKE ?")
        args.append(f"%{summary_like.strip()}%")
    if date_from:
        clauses.append("ts >= ?")
        args.append(date_from.strip())
    if date_to:
        clauses.append("ts <= ?")
        args.append(date_to.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    if limit is None or limit <= 0:
        limit_sql = ""
    else:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            raise ValidationError("limit must be a whole number") from None
        if n <= 0 or n > 10000:
            raise ValidationError("limit must be 1..10000")
        limit_sql = f" LIMIT {n}"
    sql = (f"SELECT * FROM activity_events {where} "
           f"ORDER BY ts DESC, event_id DESC{limit_sql}")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def events_for_entity(entity_type: str, entity_id: str,
                       *, limit: int = 200) -> list[Event]:
    return list_events(entity_type=entity_type,
                        entity_id=entity_id, limit=limit)


def events_for_actor(actor: str, *, limit: int = 200) -> list[Event]:
    return list_events(actor=actor, limit=limit)


def recent(limit: int = 50) -> list[Event]:
    return list_events(limit=limit)


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM activity_events WHERE event_id = ?",
            (event_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted activity event #%d", event_id)
            return True
        return False


def purge(*, older_than_days: int) -> int:
    """Delete events older than ``older_than_days`` days. Returns the
    number of rows removed."""
    init_db()
    if older_than_days <= 0:
        raise ValidationError("older_than_days must be positive")
    cutoff = (_dt.datetime.now()
              - _dt.timedelta(days=older_than_days)
              ).replace(microsecond=0).isoformat(sep=" ")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM activity_events WHERE ts < ?",
            (cutoff,))
        conn.commit()
    removed = cur.rowcount
    logger.info("Purged %d activity events older than %d days",
                removed, older_than_days)
    return removed


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    now = _dt.datetime.now()
    cutoff_24h = (now - _dt.timedelta(hours=24)
                  ).replace(microsecond=0).isoformat(sep=" ")
    cutoff_7d = (now - _dt.timedelta(days=7)
                  ).replace(microsecond=0).isoformat(sep=" ")
    cutoff_30d = (now - _dt.timedelta(days=30)
                  ).replace(microsecond=0).isoformat(sep=" ")

    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM activity_events").fetchone()[0]
        last_24h = conn.execute(
            "SELECT COUNT(*) FROM activity_events WHERE ts >= ?",
            (cutoff_24h,)).fetchone()[0]
        last_7d = conn.execute(
            "SELECT COUNT(*) FROM activity_events WHERE ts >= ?",
            (cutoff_7d,)).fetchone()[0]
        last_30d = conn.execute(
            "SELECT COUNT(*) FROM activity_events WHERE ts >= ?",
            (cutoff_30d,)).fetchone()[0]

        by_action: dict[str, int] = {}
        for r in conn.execute(
                "SELECT action, COUNT(*) n FROM activity_events "
                "GROUP BY action ORDER BY n DESC").fetchall():
            by_action[r["action"]] = r["n"]

        by_severity: dict[str, int] = {s: 0 for s in SEVERITIES}
        for r in conn.execute(
                "SELECT severity, COUNT(*) n FROM activity_events "
                "GROUP BY severity").fetchall():
            by_severity[r["severity"]] = r["n"]

        by_source: dict[str, int] = {s: 0 for s in SOURCES}
        for r in conn.execute(
                "SELECT source, COUNT(*) n FROM activity_events "
                "GROUP BY source").fetchall():
            by_source[r["source"]] = r["n"]

        by_actor: dict[str, int] = {}
        for r in conn.execute(
                "SELECT actor, COUNT(*) n FROM activity_events "
                "WHERE actor IS NOT NULL "
                "GROUP BY actor ORDER BY n DESC LIMIT 10").fetchall():
            by_actor[r["actor"]] = r["n"]

        by_entity: dict[str, int] = {}
        for r in conn.execute(
                "SELECT entity_type, COUNT(*) n FROM activity_events "
                "WHERE entity_type IS NOT NULL "
                "GROUP BY entity_type ORDER BY n DESC").fetchall():
            by_entity[r["entity_type"]] = r["n"]

        most_recent_row = conn.execute(
            "SELECT ts FROM activity_events "
            "ORDER BY ts DESC LIMIT 1").fetchone()
        most_recent_ts = most_recent_row["ts"] if most_recent_row else None

    return Summary(
        total=total,
        by_action=by_action,
        by_severity=by_severity,
        by_source=by_source,
        by_actor=by_actor,
        by_entity_type=by_entity,
        last_24h=last_24h,
        last_7d=last_7d,
        last_30d=last_30d,
        most_recent_ts=most_recent_ts,
    )
