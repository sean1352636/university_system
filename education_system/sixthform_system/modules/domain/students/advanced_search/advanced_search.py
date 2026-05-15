"""Advanced Search — cross-domain query layer for the Sixth Form System.

Searches a keyword across many of the system's tables (students, staff,
courses, subjects, class groups, behaviour log, absence requests,
attendance concerns, accommodations, safeguarding, notices, messages).

There is no per-row storage for *results* — they are computed live by
fanning out to each domain module. The persistent tables here are:

* ``saved_searches``  — named query presets (name + query + scopes
                         + filters) the user can re-run.
* ``search_history``  — a small ring of the most recent runs for
                         convenience ("recent searches").

Each search adapter is a small function that takes a query string +
filter dict and returns a list of ``Hit`` records. Hits are the
display rows: scope, label (primary), sublabel (secondary), an
entity id back-reference, and the field that matched.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ADVANCED_SEARCH_DB

DEFAULT_LIMIT_PER_SCOPE: int = 50
MAX_HISTORY_ROWS: int = 50


SCOPE_LABELS: dict[str, str] = {
    "students":             "Students",
    "staff":                "Staff",
    "courses":              "Courses",
    "subjects":             "Subjects",
    "class_groups":         "Class groups",
    "behaviour":            "Behaviour log",
    "absence_requests":     "Absence requests",
    "attendance_concerns":  "Attendance concerns",
    "accommodations":       "Accommodations",
    "safeguarding":         "Safeguarding",
    "notices":              "Notices",
    "messages":             "Messages",
}
ALL_SCOPES: tuple[str, ...] = tuple(SCOPE_LABELS.keys())
DEFAULT_SCOPES: tuple[str, ...] = ALL_SCOPES


_SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_searches (
    saved_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    query        TEXT NOT NULL DEFAULT '',
    scopes       TEXT NOT NULL DEFAULT '',
    filters      TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_history (
    history_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    query        TEXT NOT NULL,
    scopes       TEXT NOT NULL DEFAULT '',
    actor        TEXT,
    result_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sh_ts ON search_history(ts DESC);
"""


@dataclass
class Hit:
    scope: str
    entity_id: str           # opaque id (string for portability)
    label: str
    sublabel: str = ""
    matched_field: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResults:
    query: str
    scopes: list[str]
    hits_by_scope: dict[str, list[Hit]]
    total: int

    def all_hits(self) -> list[Hit]:
        return [h for hits in self.hits_by_scope.values() for h in hits]


@dataclass
class SavedSearch:
    saved_id: int
    name: str
    query: str
    scopes: list[str]
    filters: dict[str, Any]
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class HistoryEntry:
    history_id: int
    ts: str
    query: str
    scopes: list[str]
    actor: str | None
    result_count: int


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
    logger.debug("Advanced-search schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


_NAME_RE = re.compile(r"^[A-Za-z0-9 _/.\-]{1,48}$")


def _validate_scopes(scopes: Any) -> list[str]:
    if scopes is None:
        return list(DEFAULT_SCOPES)
    if isinstance(scopes, str):
        scopes = [s.strip() for s in scopes.split(",") if s.strip()]
    if not isinstance(scopes, (list, tuple)):
        raise ValidationError("scopes must be a list of scope keys")
    out: list[str] = []
    for s in scopes:
        s2 = str(s).strip()
        if s2 not in ALL_SCOPES:
            raise ValidationError(
                f"Unknown scope {s2!r}. "
                f"Valid: {', '.join(ALL_SCOPES)}")
        if s2 not in out:
            out.append(s2)
    return out or list(DEFAULT_SCOPES)


# ── Search adapters ───────────────────────────────────────────────
# Each adapter takes (query, filters) and returns list[Hit]. They
# import their dependency module lazily so this module loads cheaply.

def _trim(value: Any, n: int = 80) -> str:
    s = "" if value is None else str(value).strip()
    if not s:
        return ""
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _safe_search(label: str, fn: Callable[[], list[Hit]]) -> list[Hit]:
    try:
        return fn()
    except Exception:
        logger.exception("Search adapter %s failed", label)
        return []


def _find_field(needle: str, *fields: str) -> str:
    """Return the first non-empty field whose lowercased value
    contains ``needle``. ``""`` if none match — caller falls back."""
    n = needle.lower()
    for f in fields:
        if f and n in f.lower():
            return f
    return ""


def _search_students(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.students.students import (
        students as m,
    )
    rows = m.search_students(q) if q else m.list_students()
    out: list[Hit] = []
    needle = q.lower()
    for s in rows:
        subjects = ", ".join(getattr(s, "subjects", []) or [])
        match = _find_field(needle, s.student_id, s.full_name,
                              s.email or "", s.phone or "", subjects)
        out.append(Hit(
            scope="students",
            entity_id=s.student_id,
            label=f"{s.student_id} — {s.full_name}",
            sublabel=_trim(f"{s.email or '—'}  ·  {subjects}", 100),
            matched_field=("match: " + _trim(match, 40)) if match else "",
        ))
    return out


def _search_staff(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.staff_comms.staff import (
        staff as m,
    )
    rows = m.search_staff(q) if q else m.list_staff()
    out: list[Hit] = []
    needle = q.lower()
    for s in rows:
        full = f"{s.first_name} {s.last_name}".strip()
        match = _find_field(needle, s.staff_id, full,
                              getattr(s, "email", "") or "",
                              getattr(s, "role", "") or "",
                              getattr(s, "department", "") or "")
        out.append(Hit(
            scope="staff",
            entity_id=s.staff_id,
            label=f"{s.staff_id} — {full}",
            sublabel=_trim(f"{getattr(s, 'role', '') or '—'}  ·  "
                            f"{getattr(s, 'email', '') or '—'}", 100),
            matched_field=("match: " + _trim(match, 40)) if match else "",
        ))
    return out


def _search_courses(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.academics.courses import (
        courses as m,
    )
    rows = m.list_courses()
    out: list[Hit] = []
    if not q:
        for c in rows:
            out.append(Hit(
                scope="courses",
                entity_id=str(c.course_id),
                label=f"{c.course_code} — {c.title}",
                sublabel=_trim(getattr(c, "level", "") or "", 80),
            ))
        return out
    n = q.lower()
    for c in rows:
        bag = " ".join(
            str(v) for v in (
                c.course_code, c.title,
                getattr(c, "level", ""),
                getattr(c, "description", "") or "",
            ) if v)
        if n in bag.lower():
            out.append(Hit(
                scope="courses",
                entity_id=str(c.course_id),
                label=f"{c.course_code} — {c.title}",
                sublabel=_trim(getattr(c, "level", "") or "", 80),
            ))
    return out


def _search_subjects(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.academics.subjects import (
        subjects as m,
    )
    rows = m.list_subjects(search=q) if q else m.list_subjects()
    out: list[Hit] = []
    for s in rows:
        out.append(Hit(
            scope="subjects",
            entity_id=str(s.subject_id),
            label=s.name,
            sublabel=_trim(f"{s.qualification or '—'}  ·  "
                            f"{s.exam_board or '—'}", 80),
        ))
    return out


def _search_class_groups(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.academics.class_groups import (
        class_groups as m,
    )
    rows = m.list_groups()
    out: list[Hit] = []
    n = q.lower()
    for g in rows:
        # Fields are flexible across older/newer schemas.
        bits = []
        for fld in ("code", "name", "label", "group_code"):
            v = getattr(g, fld, None)
            if v:
                bits.append(str(v))
        title = " · ".join(bits) or f"Group #{g.group_id}"
        if not q or n in title.lower():
            out.append(Hit(
                scope="class_groups",
                entity_id=str(g.group_id),
                label=title,
                sublabel=_trim(f"course_id={getattr(g, 'course_id', '—')}",
                                60),
            ))
    return out


def _search_behaviour(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.pastoral.behaviour import (
        behaviour as m,
    )
    rows = m.list_entries()
    out: list[Hit] = []
    n = q.lower()
    for e in rows:
        bag = " ".join(str(v) for v in (
            e.description or "", e.category or "",
            e.entry_type or "", e.location or "",
            e.action_taken or "",
        ) if v)
        if not q or n in bag.lower() or n in (e.student_id or "").lower():
            out.append(Hit(
                scope="behaviour",
                entity_id=str(e.entry_id),
                label=f"#{e.entry_id} {e.student_id} · {e.entry_type}"
                       f" · {e.category}",
                sublabel=_trim(
                    f"{e.entry_date}  ·  {e.description or ''}", 110),
            ))
    return out


def _search_absence_requests(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.pastoral.absence_requests import (
        absence_requests as m,
    )
    rows = m.list_requests()
    out: list[Hit] = []
    n = q.lower()
    for r in rows:
        bag = " ".join(str(v) for v in (
            r.reason or "", r.description or "",
            r.status or "", r.submitted_by or "",
            r.notes or "",
        ) if v)
        if not q or n in bag.lower() or n in (r.student_id or "").lower():
            out.append(Hit(
                scope="absence_requests",
                entity_id=str(r.request_id),
                label=f"#{r.request_id} {r.student_id} · {r.reason}"
                       f" · {r.status}",
                sublabel=_trim(
                    f"{r.start_date} → {r.end_date}  ·  "
                    f"{r.description or ''}", 110),
            ))
    return out


def _search_attendance_concerns(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.pastoral.attendance_concerns import (
        attendance_concerns as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    n = q.lower()
    for c in rows:
        bag = " ".join(str(v) for v in (
            c.reason or "", c.description or "",
            c.action_taken or "", c.notes or "",
            c.assigned_to or "", c.raised_by or "",
        ) if v)
        if not q or n in bag.lower() or n in (c.student_id or "").lower():
            out.append(Hit(
                scope="attendance_concerns",
                entity_id=str(c.concern_id),
                label=f"#{c.concern_id} {c.student_id} · "
                       f"{c.level} · {c.status}",
                sublabel=_trim(
                    f"{c.raised_date}  ·  {c.reason}  ·  "
                    f"{c.description or ''}", 110),
            ))
    return out


def _search_accommodations(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.pastoral.accessibility import (
        accessibility as m,
    )
    rows = m.list_accommodations()
    out: list[Hit] = []
    n = q.lower()
    for a in rows:
        bag = " ".join(str(v) for v in (
            a.name or "", a.description or "",
            a.category or "", a.status or "",
            a.approved_by or "", a.notes or "",
        ) if v)
        if not q or n in bag.lower() or n in (a.student_id or "").lower():
            out.append(Hit(
                scope="accommodations",
                entity_id=str(a.accommodation_id),
                label=f"#{a.accommodation_id} {a.student_id} · {a.name}",
                sublabel=_trim(
                    f"{a.category}  ·  {a.status}  ·  "
                    f"{a.description or ''}", 110),
            ))
    return out


def _search_safeguarding(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding import (
        safeguarding as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    n = q.lower()
    for c in rows:
        # Safeguarding `Concern` field set varies; be defensive.
        bag = " ".join(str(v) for v in (
            getattr(c, "summary", "") or "",
            getattr(c, "description", "") or "",
            getattr(c, "category", "") or "",
            getattr(c, "status", "") or "",
            getattr(c, "raised_by", "") or "",
            getattr(c, "notes", "") or "",
        ) if v)
        sid = getattr(c, "student_id", "") or ""
        if not q or n in bag.lower() or n in sid.lower():
            label_bits = [
                f"#{getattr(c, 'concern_id', '?')}",
                sid or "—",
                getattr(c, "category", "") or "",
                getattr(c, "status", "") or "",
            ]
            out.append(Hit(
                scope="safeguarding",
                entity_id=str(getattr(c, "concern_id", "")),
                label=" · ".join(b for b in label_bits if b),
                sublabel=_trim(
                    getattr(c, "summary", "")
                    or getattr(c, "description", "")
                    or "", 110),
            ))
    return out


def _search_notices(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.staff_comms.notices import (
        notices as m,
    )
    rows = m.search_notices(q) if q else m.list_notices()
    out: list[Hit] = []
    for n in rows:
        body = (getattr(n, "body", "") or "")
        title = getattr(n, "title", "") or ""
        out.append(Hit(
            scope="notices",
            entity_id=str(n.notice_id),
            label=f"#{n.notice_id} {title}",
            sublabel=_trim(body, 110),
        ))
    return out


def _search_messages(q: str, _filters: dict) -> list[Hit]:
    from education_system.sixthform_system.modules.domain.staff_comms.messages import (
        messages as m,
    )
    rows = m.search_messages(q) if q else m.list_messages()
    out: list[Hit] = []
    for msg in rows:
        out.append(Hit(
            scope="messages",
            entity_id=str(msg.message_id),
            label=f"#{msg.message_id} {msg.direction or '—'} · "
                   f"{msg.subject}",
            sublabel=_trim(
                f"{(msg.sent_at or msg.received_at or msg.created_at or '')}"
                f"  ·  to {msg.to_address or msg.to_name or '—'}"
                f"  ·  {msg.body or ''}", 110),
        ))
    return out


_ADAPTERS: dict[str, Callable[[str, dict], list[Hit]]] = {
    "students":             _search_students,
    "staff":                _search_staff,
    "courses":              _search_courses,
    "subjects":             _search_subjects,
    "class_groups":         _search_class_groups,
    "behaviour":            _search_behaviour,
    "absence_requests":     _search_absence_requests,
    "attendance_concerns":  _search_attendance_concerns,
    "accommodations":       _search_accommodations,
    "safeguarding":         _search_safeguarding,
    "notices":              _search_notices,
    "messages":             _search_messages,
}


# ── Public search API ─────────────────────────────────────────────

def run_search(
    query: str,
    *,
    scopes: list[str] | tuple[str, ...] | None = None,
    filters: dict[str, Any] | None = None,
    limit_per_scope: int = DEFAULT_LIMIT_PER_SCOPE,
    record_history: bool = True,
    actor: str | None = None,
) -> SearchResults:
    """Run a query across the given scopes.

    Empty query is allowed — adapters will list everything (capped per
    scope by ``limit_per_scope``)."""
    init_db()
    scopes_use = _validate_scopes(scopes)
    filters = filters or {}
    if limit_per_scope is None or limit_per_scope <= 0:
        raise ValidationError("limit_per_scope must be positive")
    q = (query or "").strip()

    hits_by_scope: dict[str, list[Hit]] = {}
    total = 0
    for scope in scopes_use:
        adapter = _ADAPTERS[scope]
        hits = _safe_search(scope, lambda: adapter(q, filters))
        if limit_per_scope and len(hits) > limit_per_scope:
            hits = hits[:limit_per_scope]
        hits_by_scope[scope] = hits
        total += len(hits)

    if record_history:
        try:
            _record_history(q, scopes_use, actor, total)
        except Exception:
            logger.exception("Failed to record search history")

    return SearchResults(
        query=q,
        scopes=scopes_use,
        hits_by_scope=hits_by_scope,
        total=total,
    )


# ── History ───────────────────────────────────────────────────────

def _record_history(query: str, scopes: list[str],
                     actor: str | None, count: int) -> None:
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO search_history
                   (ts, query, scopes, actor, result_count)
               VALUES (?, ?, ?, ?, ?)""",
            (ts, query, ",".join(scopes), actor or None, int(count)),
        )
        # Trim to MAX_HISTORY_ROWS
        conn.execute(
            """DELETE FROM search_history
                WHERE history_id NOT IN (
                    SELECT history_id FROM search_history
                    ORDER BY ts DESC, history_id DESC
                    LIMIT ?
                )""",
            (MAX_HISTORY_ROWS,))
        conn.commit()


def list_history(limit: int = 20) -> list[HistoryEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM search_history "
            "ORDER BY ts DESC, history_id DESC LIMIT ?",
            (int(limit),)).fetchall()
    out: list[HistoryEntry] = []
    for r in rows:
        out.append(HistoryEntry(
            history_id=r["history_id"], ts=r["ts"],
            query=r["query"],
            scopes=[s for s in (r["scopes"] or "").split(",") if s],
            actor=r["actor"], result_count=r["result_count"],
        ))
    return out


def clear_history() -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM search_history")
        conn.commit()
    return cur.rowcount


# ── Saved searches ────────────────────────────────────────────────

def _saved_from_row(r: sqlite3.Row) -> SavedSearch:
    try:
        filters = json.loads(r["filters"]) if r["filters"] else {}
    except (TypeError, ValueError):
        filters = {}
    return SavedSearch(
        saved_id=r["saved_id"], name=r["name"], query=r["query"],
        scopes=[s for s in (r["scopes"] or "").split(",") if s],
        filters=filters, notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_saved_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Name must be 1–48 chars (letters, digits, "
            "space, _ . / -)")
    scopes = _validate_scopes(payload.get("scopes"))
    filters = payload.get("filters") or {}
    if isinstance(filters, str):
        s = filters.strip()
        if s:
            try:
                filters = json.loads(s)
            except ValueError as e:
                raise ValidationError(
                    f"filters is not valid JSON: {e}") from None
        else:
            filters = {}
    if not isinstance(filters, dict):
        raise ValidationError("filters must be a JSON object")
    return {
        "name": name,
        "query": (payload.get("query") or "").strip(),
        "scopes": scopes,
        "filters": json.dumps(filters) if filters else None,
        "notes": (payload.get("notes") or "").strip() or None,
    }


def create_saved_search(payload: dict[str, Any]) -> SavedSearch:
    init_db()
    p = _validate_saved_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM saved_searches WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO saved_searches
                   (name, query, scopes, filters, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_saved_search(new_id)
    assert out is not None
    logger.info("Created saved search #%d %r", new_id, p["name"])
    return out


def get_saved_search(saved_id: int) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE saved_id = ?",
            (saved_id,)).fetchone()
        return _saved_from_row(r) if r else None


def get_saved_search_by_name(name: str) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE name = ?",
            (name.strip(),)).fetchone()
        return _saved_from_row(r) if r else None


def list_saved_searches() -> list[SavedSearch]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_searches ORDER BY name ASC").fetchall()
    return [_saved_from_row(r) for r in rows]


def update_saved_search(saved_id: int,
                         payload: dict[str, Any]) -> SavedSearch:
    init_db()
    existing = get_saved_search(saved_id)
    if existing is None:
        raise ValidationError(f"No saved search #{saved_id}")
    merged = {
        "name":    payload.get("name", existing.name),
        "query":   payload.get("query", existing.query),
        "scopes":  payload.get("scopes", existing.scopes),
        "filters": payload.get("filters", existing.filters),
        "notes":   payload.get("notes", existing.notes),
    }
    p = _validate_saved_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT saved_id FROM saved_searches WHERE name = ?",
            (p["name"],)).fetchone()
        if row and row["saved_id"] != saved_id:
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        conn.execute(
            """UPDATE saved_searches SET
                   name = ?, query = ?, scopes = ?, filters = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE saved_id = ?""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"], saved_id),
        )
        conn.commit()
    out = get_saved_search(saved_id)
    assert out is not None
    logger.info("Updated saved search #%d %r", saved_id, p["name"])
    return out


def delete_saved_search(saved_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM saved_searches WHERE saved_id = ?",
            (saved_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted saved search #%d", saved_id)
            return True
        return False


def run_saved_search(saved_id: int, *,
                     actor: str | None = None) -> SearchResults:
    s = get_saved_search(saved_id)
    if s is None:
        raise ValidationError(f"No saved search #{saved_id}")
    return run_search(
        s.query, scopes=s.scopes, filters=s.filters,
        actor=actor,
    )
