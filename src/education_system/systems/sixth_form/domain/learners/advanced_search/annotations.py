"""Result annotations and the operator action log for Advanced Search.

Tags, flags, notes, an owner, a workflow assignment and duplicate-merge
links are overlay metadata keyed by (scope, entity_id). They are kept in
the advanced-search database, never in the records themselves, so they
are shared between users and machines and recorded with who set them.

Both used to be JSON files in the sixth form data directory. The first
read imports anything still in those files; the files are left in place.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from education_system import paths

from ._db import _connect, init_db, logger

_LEGACY_ANN_FILE = "advanced_search_annotations.json"
_LEGACY_LOG_FILE = "advanced_search_action_log.json"
_IMPORT_MARK = "_legacy_json_import"
_MAX_ACTION_ROWS = 5000


def _now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _actor() -> str | None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or None


def key(scope: str, entity_id: str) -> str:
    return f"{scope}:{entity_id}"


def _split(k: str) -> tuple[str, str]:
    scope, _, entity_id = k.partition(":")
    return scope, entity_id


_IMPORTED = False


def _import_legacy() -> None:
    """Copy the old JSON files in once (marked in search_index_meta)."""
    global _IMPORTED
    if _IMPORTED:
        return
    init_db()
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM search_index_meta WHERE scope = ?",
                        (_IMPORT_MARK,)).fetchone():
            _IMPORTED = True
            return
        ann = _read_json(_LEGACY_ANN_FILE, dict)
        for k, data in ann.items():
            if isinstance(data, dict) and ":" in k:
                scope, entity_id = _split(k)
                conn.execute(
                    "INSERT OR IGNORE INTO result_annotations "
                    "(scope, entity_id, data_json, updated_by, updated_at) "
                    "VALUES (?, ?, ?, NULL, ?)",
                    (scope, entity_id, json.dumps(data), _now()))
        for row in _read_json(_LEGACY_LOG_FILE, list):
            if isinstance(row, dict):
                conn.execute(
                    "INSERT INTO search_action_log "
                    "(ts, actor, action, detail, count) VALUES (?, NULL, ?, ?, ?)",
                    (row.get("ts") or _now(), str(row.get("action") or "?"),
                     str(row.get("detail") or ""), int(row.get("count") or 0)))
        conn.execute(
            "INSERT OR REPLACE INTO search_index_meta "
            "(scope, indexed_rows, last_refresh) VALUES (?, ?, ?)",
            (_IMPORT_MARK, len(ann), _now()))
        conn.commit()
    _IMPORTED = True


def _read_json(name: str, kind: type) -> Any:
    try:
        with open(paths.SIXTH_FORM_DATA_DIR / name, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, kind) else kind()
    except (OSError, ValueError):
        return kind()


# ── Annotations ───────────────────────────────────────────────────

def load_all() -> dict[str, dict]:
    """Every annotation, keyed ``"scope:entity_id"``."""
    _import_legacy()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT scope, entity_id, data_json FROM result_annotations"
        ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        try:
            out[key(r["scope"], r["entity_id"])] = json.loads(r["data_json"])
        except ValueError:
            continue
    return out


def get(scope: str, entity_id: str) -> dict:
    _import_legacy()
    with _connect() as conn:
        r = conn.execute(
            "SELECT data_json FROM result_annotations "
            "WHERE scope = ? AND entity_id = ?", (scope, entity_id)).fetchone()
    try:
        return json.loads(r["data_json"]) if r else {}
    except ValueError:
        return {}


def save_all(store: dict[str, dict]) -> None:
    """Make the table match *store*: changed keys are written (stamped with
    the signed-in user), keys no longer present are removed."""
    before = load_all()
    who = _actor()
    with _connect() as conn:
        for k, data in store.items():
            if ":" not in k or before.get(k) == data:
                continue
            scope, entity_id = _split(k)
            if data:
                conn.execute(
                    "INSERT INTO result_annotations "
                    "(scope, entity_id, data_json, updated_by, updated_at) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(scope, entity_id) DO "
                    "UPDATE SET data_json = excluded.data_json, "
                    "updated_by = excluded.updated_by, "
                    "updated_at = excluded.updated_at",
                    (scope, entity_id, json.dumps(data), who, _now()))
            else:
                conn.execute("DELETE FROM result_annotations "
                             "WHERE scope = ? AND entity_id = ?",
                             (scope, entity_id))
        for k in set(before) - set(store):
            scope, entity_id = _split(k)
            conn.execute("DELETE FROM result_annotations "
                         "WHERE scope = ? AND entity_id = ?", (scope, entity_id))
        conn.commit()


# ── Operator action log ───────────────────────────────────────────

def log_action(action: str, detail: str = "", count: int = 0) -> None:
    """Record what an operator did with results. Never raises: a lost log
    line must not break the action it was recording."""
    try:
        _import_legacy()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO search_action_log (ts, actor, action, detail, count) "
                "VALUES (?, ?, ?, ?, ?)",
                (_now(), _actor(), action, detail or "", int(count or 0)))
            conn.execute(
                "DELETE FROM search_action_log WHERE action_id NOT IN ("
                "SELECT action_id FROM search_action_log "
                "ORDER BY action_id DESC LIMIT ?)", (_MAX_ACTION_ROWS,))
            conn.commit()
    except Exception:
        logger.warning("could not write the advanced-search action log",
                       exc_info=True)


def list_actions(limit: int = 200) -> list[dict[str, Any]]:
    """Recent actions, oldest first. Without the governance capability a
    signed-in user sees only their own."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    _import_legacy()
    p = access.current()
    with _connect() as conn:
        if p.username and not p.can("governance"):
            rows = conn.execute(
                "SELECT * FROM search_action_log WHERE actor = ? "
                "ORDER BY action_id DESC LIMIT ?",
                (p.username, int(limit))).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM search_action_log "
                "ORDER BY action_id DESC LIMIT ?", (int(limit),)).fetchall()
    return [{"ts": r["ts"], "actor": r["actor"], "action": r["action"],
             "detail": r["detail"], "count": r["count"]}
            for r in reversed(rows)]
