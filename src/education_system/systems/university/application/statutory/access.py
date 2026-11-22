"""Who may prepare the university's statutory returns, and their audit trail.

HESA, SLC, UCAS, UKVI and Graduate Outcomes returns carry personal data for
every student, so they belong to administrators and the registry (role
``registrar`` / ``registry``). Everyone else is refused. Every build, import,
export and status change is written to ``statutory_audit``.

Helpers here take an open connection and do not commit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.infrastructure.database.schemas import (
    statutory_returns_schema as schema,
)

ROLES = ("admin", "administrator", "superadmin", "registrar", "registry")


@dataclass(frozen=True)
class Officer:
    """The signed-in person preparing a return."""

    username: str
    role: str

    @property
    def allowed(self) -> bool:
        return self.role in ROLES


def officer(current) -> Officer:
    """An :class:`Officer` from a session dict (``auth.current_user``) or an
    Officer; refuses anyone outside the admin/registry roles."""
    if isinstance(current, Officer):
        who = current
    else:
        current = current or {}
        who = Officer(username=str(current.get("username") or current.get("id") or "").strip(),
                      role=str(current.get("role") or "").strip().lower())
    if not who.username or not who.allowed:
        raise PermissionError("Statutory returns are for administrators and the registry only")
    return who


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


def session():
    """A transaction with the statutory schema applied."""
    return _Session()


class _Session:
    def __enter__(self):
        self._cm = transaction()
        conn = self._cm.__enter__()
        ensure(conn)
        return conn

    def __exit__(self, *exc):
        return self._cm.__exit__(*exc)


def dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def one(conn, sql, params=()) -> dict | None:
    rows = dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                        (name,)).fetchone() is not None


def columns(conn, table) -> set:
    if not has_table(conn, table):
        return set()
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_date(value, label, required=True) -> str | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None


def audit(conn, who: Officer, area, entity, entity_id, action, detail=None) -> None:
    conn.execute(
        "INSERT INTO statutory_audit (area, entity, entity_id, action, actor, detail_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (area, entity, None if entity_id is None else str(entity_id), action, who.username,
         json.dumps(detail, default=str, sort_keys=True) if detail is not None else None))


def audit_trail(current, area=None, limit=200) -> list[dict]:
    officer(current)
    with session() as conn:
        if area:
            return dicts(conn.execute("SELECT * FROM statutory_audit WHERE area = ? "
                                      "ORDER BY audit_id DESC LIMIT ?", (area, limit)))
        return dicts(conn.execute("SELECT * FROM statutory_audit ORDER BY audit_id DESC LIMIT ?",
                                  (limit,)))


def student_name(row: dict) -> str:
    return " ".join(p for p in (row.get("first_name"), row.get("last_name")) if p).strip()


__all__ = ["ROLES", "Officer", "audit", "audit_trail", "columns", "dicts", "ensure",
           "has_table", "iso_date", "now", "officer", "one", "session", "stamp", "student_name"]
