"""Shared record plumbing for the pastoral data layers.

Several pastoral modules grew child records (PEP reviews, EHCP annual
reviews, healthcare plans, medication administrations, appeal hearings,
contact attempts ...). Each one is a plain table with validated
columns. Rather than repeat the same validate / insert / update /
select code for every table, a module declares a :class:`TableSpec`
(its columns and the dataclass a row maps to) and calls the helpers
here with its own connection and its own ``ValidationError`` class.

The interfaces read the same specs to build their forms, so a column
added here shows up in the GUI form and the CLI prompts together.

This module never opens a database itself: the caller passes the
connection, so it stays on whatever DB file the owning module uses.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, fields as _dc_fields
from typing import Any, Callable, Iterable

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

#: Column kinds understood by :func:`validate` and the form builders.
KINDS = ("text", "multiline", "date", "time", "int", "money", "bool",
         "choice", "student")


@dataclass(frozen=True)
class Col:
    """One editable column of a record table."""
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    choices: tuple[str, ...] = ()
    default: Any = None
    min_value: float | None = None
    max_value: float | None = None
    #: Shown in list views (GUI table / CLI listing).
    listed: bool = True
    #: Not editable after creation (e.g. the student a record is for).
    fixed: bool = False
    #: Filled in by the domain code, never shown on a form.
    hidden: bool = False


@dataclass(frozen=True)
class TableSpec:
    table: str
    id_col: str
    cols: tuple[Col, ...]
    row_type: type
    label: str
    order_by: str
    created_col: str | None = "created_at"
    updated_col: str | None = "updated_at"

    def col(self, name: str) -> Col:
        for c in self.cols:
            if c.name == name:
                return c
        raise KeyError(name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.cols)


def today() -> str:
    return _dt.date.today().isoformat()


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def check_date(value: Any, label: str, error: type[Exception]) -> str | None:
    if _blank(value):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise error(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise error(f"{label} is not a real calendar date") from None
    return s


def coerce_bool(v: Any) -> int:
    if isinstance(v, bool):
        return 1 if v else 0
    if v in (None, ""):
        return 0
    if isinstance(v, (int, float)):
        return 1 if v else 0
    return 1 if str(v).strip().lower() in (
        "1", "y", "yes", "true", "t", "on") else 0


def _validate_value(col: Col, value: Any, error: type[Exception],
                    student_exists: Callable[[str], bool] | None) -> Any:
    if _blank(value):
        if col.kind == "bool":
            return coerce_bool(col.default)
        if col.default is not None:
            value = col.default() if callable(col.default) else col.default
        if _blank(value):
            if col.required:
                raise error(f"{col.label} is required")
            return None
    k = col.kind
    if k in ("text", "multiline"):
        return str(value).strip()
    if k == "date":
        return check_date(value, col.label, error)
    if k == "time":
        s = str(value).strip()
        if not _TIME_RE.match(s):
            raise error(f"{col.label} must be HH:MM")
        hh, mm = int(s[:2]), int(s[3:])
        if hh > 23 or mm > 59:
            raise error(f"{col.label} is not a real time")
        return s
    if k == "int":
        try:
            n = int(str(value).strip())
        except (TypeError, ValueError):
            raise error(f"{col.label} must be a whole number") from None
        if col.min_value is not None and n < col.min_value:
            raise error(f"{col.label} must be at least {col.min_value:g}")
        if col.max_value is not None and n > col.max_value:
            raise error(f"{col.label} must be at most {col.max_value:g}")
        return n
    if k == "money":
        try:
            n = round(float(str(value).strip().lstrip("£")
                            .replace(",", "")), 2)
        except (TypeError, ValueError):
            raise error(f"{col.label} must be an amount in pounds") from None
        if n < 0:
            raise error(f"{col.label} cannot be negative")
        return n
    if k == "bool":
        return coerce_bool(value)
    if k == "choice":
        s = str(value).strip()
        if s not in col.choices:
            raise error(f"{col.label} must be one of: "
                        f"{', '.join(col.choices)}")
        return s
    if k == "student":
        s = str(value).strip()
        if student_exists is not None and not student_exists(s):
            raise error(f"No student with id {s}")
        return s
    raise error(f"Unknown column kind {k!r} for {col.label}")


def validate(spec: TableSpec, data: dict[str, Any], *,
             error: type[Exception],
             existing: Any = None,
             student_exists: Callable[[str], bool] | None = None,
             ) -> dict[str, Any]:
    """Validate *data* against *spec*.

    With *existing* (a row dataclass), keys missing from *data* keep
    their current value and ``fixed`` columns cannot change.
    """
    out: dict[str, Any] = {}
    for col in spec.cols:
        if existing is not None and (col.fixed or col.name not in data):
            out[col.name] = getattr(existing, col.name)
            continue
        out[col.name] = _validate_value(col, data.get(col.name), error,
                                        student_exists)
    return out


def to_row(spec: TableSpec, r: Any) -> Any:
    keys = set(r.keys())
    kwargs = {}
    for f in _dc_fields(spec.row_type):
        v = r[f.name] if f.name in keys else None
        col = next((c for c in spec.cols if c.name == f.name), None)
        if col is not None and col.kind == "bool":
            v = bool(v)
        kwargs[f.name] = v
    return spec.row_type(**kwargs)


def insert(conn: Any, spec: TableSpec, values: dict[str, Any]) -> int:
    names = [c for c in spec.names if c in values]
    cols = list(names)
    marks = ["?"] * len(names)
    args = [values[c] for c in names]
    for ts in (spec.created_col, spec.updated_col):
        if ts:
            cols.append(ts)
            marks.append("?")
            args.append(now())
    # Identifiers come from the module's own TableSpec, never from input.
    sql = (f"INSERT INTO {spec.table} ({', '.join(cols)}) "  # DBW001: spec identifiers
           f"VALUES ({', '.join(marks)})")
    cur = conn.execute(sql, args)
    return int(cur.lastrowid)


def update(conn: Any, spec: TableSpec, row_id: int,
           values: dict[str, Any]) -> None:
    names = [c for c in spec.names if c in values]
    sets = [f"{c} = ?" for c in names]
    args: list[Any] = [values[c] for c in names]
    if spec.updated_col:
        sets.append(f"{spec.updated_col} = ?")
        args.append(now())
    if not sets:
        return
    args.append(row_id)
    conn.execute(
        f"UPDATE {spec.table} SET {', '.join(sets)} "  # DBW001: spec identifiers
        f"WHERE {spec.id_col} = ?", args)


def fetch(conn: Any, spec: TableSpec, row_id: int) -> Any:
    r = conn.execute(
        f"SELECT * FROM {spec.table} WHERE {spec.id_col} = ?",  # DBW001: spec identifiers
        (row_id,)).fetchone()
    return to_row(spec, r) if r else None


def select(conn: Any, spec: TableSpec, *,
           equals: dict[str, Any] | None = None,
           where: Iterable[str] = (), args: Iterable[Any] = (),
           order_by: str | None = None, limit: int | None = None,
           ) -> list[Any]:
    clauses: list[str] = []
    params: list[Any] = []
    for k, v in (equals or {}).items():
        if v in (None, ""):
            continue
        if k not in spec.names and k != spec.id_col:
            raise KeyError(k)
        clauses.append(f"{k} = ?")
        params.append(v)
    clauses.extend(where)
    params.extend(args)
    sql = f"SELECT * FROM {spec.table}"  # DBW001: spec identifiers
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {order_by or spec.order_by}"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return [to_row(spec, r) for r in conn.execute(sql, params).fetchall()]


def delete(conn: Any, spec: TableSpec, row_id: int) -> bool:
    cur = conn.execute(
        f"DELETE FROM {spec.table} WHERE {spec.id_col} = ?",  # DBW001: spec identifiers
        (row_id,))
    return cur.rowcount > 0


def ensure_columns(conn: Any, table: str, columns: dict[str, str]) -> None:
    """``ALTER TABLE ... ADD COLUMN`` for each missing column."""
    have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}  # DBW001: fixed table names
    for name, decl in columns.items():
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")  # DBW001: fixed names


def table_exists(conn: Any, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone() is not None


# ── Access helpers ───────────────────────────────────────────────

def guard(capability: str, area: str, action: str, *,
          student_id: str | None = None,
          record_ref: str | None = None) -> Any:
    """Require *capability* of the signed-in principal and audit the
    access. When *student_id* is given, the object-level
    :func:`access.can_see_student` check must also pass.

    Returns the principal so callers can stamp ``recorded_by``.
    """
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    cap = getattr(access, capability)
    if not p.can(cap):
        access.log_sensitive_access(p, area, action, student_id=student_id,
                                    record_ref=record_ref, allowed=False)
        p.require(cap, action)
    if student_id and not access.can_see_student(p, student_id,
                                                 capability=cap):
        access.log_sensitive_access(p, area, action, student_id=student_id,
                                    record_ref=record_ref, allowed=False)
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not see {area} records "
            f"for student {student_id}.")
    access.log_sensitive_access(p, area, action, student_id=student_id,
                                record_ref=record_ref)
    return p


def visible_filter(capability: str, rows: list[Any],
                   attr: str = "student_id") -> list[Any]:
    """Drop rows for students the principal may not see."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    cap = getattr(access, capability)
    seen: dict[str, bool] = {}
    out = []
    for r in rows:
        sid = getattr(r, attr, None)
        if sid is None:
            out.append(r)
            continue
        if sid not in seen:
            seen[sid] = access.can_see_student(p, sid, capability=cap)
        if seen[sid]:
            out.append(r)
    return out


def current_username() -> str | None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    return p.staff_name or p.username or None
