"""DB plumbing, validation and all mutable module state (owner) for Advanced Search.

Owns DB_PATH, _DB_READY, the FTS availability flag and the result cache;
the facade forwards attribute writes for these names here.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (  # noqa: F401
    ALL_SCOPES,
    DEFAULT_SCOPES,
    ValidationError,
)

logger = logging.getLogger("education_system.systems.sixth_form.domain.learners.advanced_search.advanced_search")

DB_PATH = paths.SIXTH_FORM_ADVANCED_SEARCH_DB


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

CREATE TABLE IF NOT EXISTS pinned_results (
    pin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    actor        TEXT NOT NULL,
    scope        TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE (actor, scope, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_pr_actor ON pinned_results(actor);

CREATE TABLE IF NOT EXISTS scheduled_searches (
    schedule_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    saved_id         INTEGER NOT NULL,
    cron             TEXT NOT NULL DEFAULT 'daily',
    notify_actor     TEXT,
    last_run_at      TEXT,
    last_count       INTEGER NOT NULL DEFAULT 0,
    new_since_last   INTEGER NOT NULL DEFAULT 0,
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (saved_id) REFERENCES saved_searches(saved_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ss_saved ON scheduled_searches(saved_id);

CREATE TABLE IF NOT EXISTS subscription_notifications (
    notif_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id   INTEGER NOT NULL,
    actor         TEXT NOT NULL,
    delta         INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    sample_scope  TEXT,
    sample_label  TEXT,
    sample_entity TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    read_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sn_actor
    ON subscription_notifications(actor, read_at);

CREATE TABLE IF NOT EXISTS search_index_meta (
    scope          TEXT PRIMARY KEY,
    indexed_rows   INTEGER NOT NULL DEFAULT 0,
    last_refresh   TEXT
);

CREATE TABLE IF NOT EXISTS cohorts (
    cohort_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    owner_actor  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cohort_members (
    cohort_id    INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    added_at     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (cohort_id, student_id),
    FOREIGN KEY (cohort_id) REFERENCES cohorts(cohort_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cm_cohort ON cohort_members(cohort_id);

CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    owner_actor  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dashboard_items (
    dashboard_id INTEGER NOT NULL,
    saved_id     INTEGER NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (dashboard_id, saved_id),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_audit (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    actor            TEXT,
    role             TEXT,
    query            TEXT NOT NULL DEFAULT '',
    scopes           TEXT NOT NULL DEFAULT '',
    sensitive_scopes TEXT NOT NULL DEFAULT '',
    break_glass      INTEGER NOT NULL DEFAULT 0,
    reason           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sa_ts ON search_audit(ts DESC);

-- Tags, flags, notes, owner, workflow and merge links laid over results.
-- One JSON document per record; overlay data only, never written into
-- the records themselves.
CREATE TABLE IF NOT EXISTS result_annotations (
    scope        TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    data_json    TEXT NOT NULL DEFAULT '{}',
    updated_by   TEXT,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (scope, entity_id)
);

-- What operators did with results (exports, messages, bulk edits).
CREATE TABLE IF NOT EXISTS search_action_log (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    actor        TEXT,
    action       TEXT NOT NULL,
    detail       TEXT NOT NULL DEFAULT '',
    count        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sal_ts ON search_action_log(ts DESC);
"""


# Columns added to search_history over time (telemetry).
_SEARCH_HISTORY_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("elapsed_ms_json",   "TEXT"),
    ("result_count_json", "TEXT"),
    ("zero_result",       "INTEGER NOT NULL DEFAULT 0"),
)


# Columns added to saved_searches over time. Applied as ALTER TABLE
# at init_db() so existing DBs upgrade transparently.
_SAVED_SEARCH_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("owner_actor", "TEXT"),
    ("visibility",  "TEXT NOT NULL DEFAULT 'private'"),
    ("role_acl",    "TEXT"),
    ("folder",      "TEXT"),
    ("tags",        "TEXT"),
)

# Columns added to scheduled_searches (thresholds + delta snapshots).
_SCHEDULED_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("threshold",     "INTEGER NOT NULL DEFAULT 0"),
    ("last_keys_json", "TEXT"),
)

# Columns added to subscription_notifications (snooze).
_NOTIF_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("snoozed_until", "TEXT"),
)

# Columns added to search_audit (exports and mail-merges are audited too).
_AUDIT_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("action",       "TEXT NOT NULL DEFAULT 'search'"),
    ("record_count", "INTEGER"),
)


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {r["name"] for r in conn.execute(
            "PRAGMA table_info(saved_searches)").fetchall()}
        for col, ddl in _SAVED_SEARCH_EXTRA_COLS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE saved_searches ADD COLUMN {col} {ddl}")
        existing_h = {r["name"] for r in conn.execute(
            "PRAGMA table_info(search_history)").fetchall()}
        for col, ddl in _SEARCH_HISTORY_EXTRA_COLS:
            if col not in existing_h:
                conn.execute(
                    f"ALTER TABLE search_history ADD COLUMN {col} {ddl}")
        for table, cols in (("scheduled_searches", _SCHEDULED_EXTRA_COLS),
                            ("subscription_notifications", _NOTIF_EXTRA_COLS),
                            ("search_audit", _AUDIT_EXTRA_COLS)):
            have = {r["name"] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            for col, ddl in cols:
                if col not in have:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.commit()
    _ensure_fts_index()
    logger.debug("Advanced-search schema ready at %s", DB_PATH)
    _DB_READY = True


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
                f"Unknown scope {s2!r}. Valid: {', '.join(ALL_SCOPES)}")
        if s2 not in out:
            out.append(s2)
    return out or list(DEFAULT_SCOPES)


# ══════════════════════════════════════════════════════════════════
# FTS5 mirror index (item 47)
# ══════════════════════════════════════════════════════════════════

_FTS_AVAILABLE: bool | None = None
_FTS_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts "
    "USING fts5(scope UNINDEXED, entity_id UNINDEXED, text, "
    "tokenize='porter unicode61')")


def _fts_available() -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with _connect() as conn:
            conn.execute(_FTS_DDL)
            conn.commit()
        _FTS_AVAILABLE = True
    except db.OperationalError:
        logger.warning("SQLite FTS5 not available — falling back to LIKE")
        _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _ensure_fts_index() -> None:
    # Create the virtual table idempotently in the *current* DB. The
    # availability flag is cached process-wide, but the table itself lives
    # per-file — so always (re)issue the DDL when FTS is available.
    if _fts_available():
        try:
            with _connect() as conn:
                conn.execute(_FTS_DDL)
                conn.commit()
        except db.OperationalError:
            pass


# ══════════════════════════════════════════════════════════════════
# Cache (item 48)
# ══════════════════════════════════════════════════════════════════

_CACHE: dict[tuple, tuple[float, SearchResults]] = {}
CACHE_TTL_SECONDS: float = 30.0
_CACHE_MAX_ENTRIES: int = 64
_CACHE_HITS: int = 0
_CACHE_MISSES: int = 0


def _cache_key(query: str, scopes: list[str],
               filters: dict[str, Any], opts: QueryOptions,
               actor: str | None, flags: tuple) -> tuple:
    return (
        query, tuple(scopes), repr(sorted(filters.items())),
        (opts.fuzzy_default, opts.use_stemming, opts.ignore_stopwords,
         opts.expand_synonyms, opts.fold_diacritics,
         opts.today.isoformat() if opts.today else None),
        actor or "", flags,
    )


def _cache_get(key: tuple) -> SearchResults | None:
    global _CACHE_HITS, _CACHE_MISSES
    rec = _CACHE.get(key)
    if rec is None:
        _CACHE_MISSES += 1
        return None
    ts, r = rec
    if _now() - ts > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        _CACHE_MISSES += 1
        return None
    _CACHE_HITS += 1
    return r


def _cache_put(key: tuple, r: SearchResults) -> None:
    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
    _CACHE[key] = (_now(), r)


def clear_cache() -> None:
    global _CACHE_HITS, _CACHE_MISSES
    _CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_MISSES = 0


def cache_stats() -> dict[str, Any]:
    """Live session cache counters (item 43)."""
    total = _CACHE_HITS + _CACHE_MISSES
    return {
        "entries": len(_CACHE),
        "max_entries": _CACHE_MAX_ENTRIES,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
        "hit_rate": round(_CACHE_HITS / total, 3) if total else 0.0,
    }


def _now() -> float:
    import time as _t
    return _t.monotonic()
