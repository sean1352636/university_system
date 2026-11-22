"""The one record layer every local authority education area is built on.

An area declares a :class:`RecordType` - its fields and its rules - and gets,
from here: its table (created, and new columns added, on first use), checked
and normalised saves, list/search/filter, delete with a friendly refusal when
other records still point at the row, and a line in the change history (which
is also each child's chronology).

Field kinds:

``text`` ``long`` (multi-line) ``number`` ``date`` (stored ISO ``YYYY-MM-DD``; ``DD/MM/YYYY``
accepted) ``choice`` ``int`` ``money`` ``bool`` ``learner`` (a child on the
register; the table is named ``learners``) ``ref`` (a row of another record type, ``ref=<key>``).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from typing import Any, Callable, Iterable

from education_system.systems.local_authority.infrastructure import database as db

logger = logging.getLogger(__name__)

KINDS = frozenset({"text", "long", "date", "choice", "int", "number", "money", "bool",
                   "learner", "ref"})
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


class ValidationError(ValueError):
    """A save broke a rule; the message is shown to the user as-is."""


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str = "text"
    choices: tuple[str, ...] = ()
    required: bool = False
    listed: bool = True           # shown as a column in the record list
    default: Any = None           # value (or zero-arg callable) a new record starts with
    ref: str | None = None        # kind "ref": the record type it points at
    on_delete: str = "RESTRICT"   # kind "ref"/"learner": what deleting the target does
    help: str = ""                # one-line hint under the form field
    form: bool = True             # False: worked out by the area's rules, not typed in

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown field kind {self.kind!r}")
        if not _IDENT.match(self.name):
            raise ValueError(f"bad field name {self.name!r}")
        if self.kind == "ref" and not self.ref:
            raise ValueError(f"ref field {self.name!r} needs ref=")

    def initial(self) -> Any:
        return self.default() if callable(self.default) else self.default


#: (column label, function of the row) - shown in lists, never stored.
Computed = tuple[str, Callable[[dict], str]]


@dataclass
class RecordType:
    key: str                                   # table name
    title: str                                 # plural heading, e.g. "Provision"
    singular: str                              # e.g. "provision"
    fields: tuple[Field, ...]
    order_by: str = "id DESC"
    describe: Callable[[dict], str] | None = None
    #: Called with (new values, old row or None) before a save. Raise
    #: ValidationError to refuse; may fill derived fields in *values*.
    check: Callable[[dict, dict | None], None] | None = None
    #: Called with (connection, saved row, old row or None) inside the save's
    #: transaction, for knock-on updates to other tables.
    after_save: Callable[[sqlite3.Connection, dict, dict | None], None] | None = None
    #: Called with (saved row, old row or None) once the save has committed -
    #: for work outside this database (the platform's linked primary and
    #: secondary schools). It can't undo the save: what it raises is
    #: logged and kept as a notice (:func:`take_notices`); what it returns
    #: (lines) is kept too.
    after_commit: Callable[[dict, dict | None], list[str] | None] | None = None
    computed: tuple[Computed, ...] = ()
    #: Choice fields offered as filters above the list.
    filters: tuple[str, ...] = ()
    fields_by_name: dict[str, Field] = dc_field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not _IDENT.match(self.key):
            raise ValueError(f"bad record type key {self.key!r}")
        self.fields_by_name = {f.name: f for f in self.fields}
        REGISTRY[self.key] = self
        db.register_setup(f"table:{self.key}", self._ensure_table)

    @property
    def learner_field(self) -> Field | None:
        return next((f for f in self.fields if f.kind == "learner"), None)

    def label_for(self, row: dict) -> str:
        if self.describe is not None:
            return self.describe(row)
        first = self.fields[0].name
        return str(row.get(first) or f"{self.singular} #{row.get('id')}")

    # ── table ────────────────────────────────────────────────────────
    def _column_sql(self, f: Field) -> str:
        if f.kind == "learner":
            return (f"{f.name} INTEGER {'NOT NULL ' if f.required else ''}"
                    f"REFERENCES learners(id) ON DELETE {f.on_delete}")
        if f.kind == "ref":
            return (f"{f.name} INTEGER {'NOT NULL ' if f.required else ''}"
                    f"REFERENCES {f.ref}(id) ON DELETE {f.on_delete}")
        sql_type = {"int": "INTEGER", "bool": "INTEGER", "money": "REAL",
                    "number": "REAL"}.get(f.kind, "TEXT")
        return f"{f.name} {sql_type}"

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        cols = ",\n  ".join(self._column_sql(f) for f in self.fields)
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self.key} (\n"
            f"  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  {cols},\n"
            "  created_at TEXT NOT NULL DEFAULT (datetime('now')),\n"
            "  updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({self.key})")}
        for f in self.fields:
            if f.name not in have:   # a field added after the table was made
                # SQLite can't ADD a NOT NULL/REFERENCES column without a default.
                sql_type = "INTEGER" if f.kind in ("learner", "ref", "int", "bool") else (
                    "REAL" if f.kind in ("money", "number") else "TEXT")
                conn.execute(f"ALTER TABLE {self.key} ADD COLUMN {f.name} {sql_type}")
        lf = self.learner_field
        if lf is not None:
            conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{self.key}_{lf.name} "
                         f"ON {self.key}({lf.name})")


#: Every record type by key (filled as area modules are imported).
REGISTRY: dict[str, RecordType] = {}


# ── values ───────────────────────────────────────────────────────────

def parse_date(value: Any) -> str | None:
    """ISO date string from ISO, ``DD/MM/YYYY`` or a date; ``None`` if blank."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValidationError(f"'{text}' is not a date - use YYYY-MM-DD or DD/MM/YYYY.")


def to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _normalise(rt: RecordType, raw: dict) -> dict:
    out: dict[str, Any] = {}
    for f in rt.fields:
        if f.name not in raw:
            continue
        value = raw[f.name]
        if isinstance(value, str):
            value = value.strip()
        try:
            if value in (None, ""):
                value = 0 if f.kind == "bool" else None
            elif f.kind == "date":
                value = parse_date(value)
            elif f.kind in ("int", "learner", "ref"):
                value = int(value)
            elif f.kind in ("money", "number"):
                value = round(float(str(value).replace("£", "").replace(",", "")), 2)
                if value < 0:
                    raise ValidationError(f"{f.label} can't be negative.")
            elif f.kind == "bool":
                value = 1 if value in (True, 1, "1", "yes", "Yes", "true", "True") else 0
            elif f.kind == "choice" and value not in f.choices:
                raise ValidationError(f"{f.label} must be one of: {', '.join(f.choices)}.")
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"{f.label}: '{raw[f.name]}' isn't a valid value.") from None
        out[f.name] = value
    return out


# ── reads ────────────────────────────────────────────────────────────

def _select(rt: RecordType) -> str:
    lf = rt.learner_field
    if lf is None:
        return f"SELECT t.* FROM {rt.key} t"
    return (f"SELECT t.*, l.first_name || ' ' || l.last_name AS learner_name "
            f"FROM {rt.key} t LEFT JOIN learners l ON l.id = t.{lf.name}")


def list_records(rt: RecordType, *, learner_id: int | None = None,
                 equals: dict[str, Any] | None = None, search: str = "",
                 limit: int | None = None) -> list[dict]:
    """Rows of *rt*, newest/ordered first, optionally for one learner,
    matching exact field values and containing *search* in any text field."""
    sql, args = _select(rt), []
    where: list[str] = []
    lf = rt.learner_field
    if learner_id is not None and lf is not None:
        where.append(f"t.{lf.name} = ?")
        args.append(learner_id)
    for name, value in (equals or {}).items():
        if name not in rt.fields_by_name:
            raise KeyError(name)
        where.append(f"t.{name} = ?")
        args.append(value)
    if search.strip():
        cols = [f"t.{f.name}" for f in rt.fields if f.kind in ("text", "long", "choice")]
        if lf is not None:
            cols.append("l.first_name || ' ' || l.last_name")
        if cols:
            where.append("(" + " OR ".join(f"{c} LIKE ?" for c in cols) + ")")
            args.extend([f"%{search.strip()}%"] * len(cols))
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = ", ".join(f"t.{part.strip()}" for part in rt.order_by.split(","))
    sql += f" ORDER BY {order}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def get(rt: RecordType, record_id: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(_select(rt) + " WHERE t.id = ?", (record_id,)).fetchone()
    return dict(row) if row else None


def options(rt: RecordType, *, learner_id: int | None = None) -> list[tuple[int, str]]:
    """``(id, label)`` pairs for a picker."""
    return [(r["id"], rt.label_for(r)) for r in list_records(rt, learner_id=learner_id)]


# ── writes ───────────────────────────────────────────────────────────

def save(rt: RecordType, values: dict, *, record_id: int | None = None,
         actor: str = "system") -> int:
    """Create (``record_id=None``) or update a record. Returns its id.

    Raises:
        ValidationError: a required field is empty, a value is malformed, or
            one of the area's rules refused it.
    """
    old = get(rt, record_id) if record_id is not None else None
    if record_id is not None and old is None:
        raise ValidationError(f"That {rt.singular} no longer exists.")
    if old is None:   # a new record starts from each field's default
        values = {**{f.name: f.initial() for f in rt.fields if f.default is not None},
                  **{k: v for k, v in values.items() if v not in (None, "")}}
    clean = _normalise(rt, values)
    merged = {**(old or {}), **clean}
    for f in rt.fields:
        if f.required and merged.get(f.name) in (None, ""):
            raise ValidationError(f"{f.label} is required.")
    if rt.check is not None:
        rt.check(clean, old)   # may add derived fields to clean
        clean = _normalise(rt, clean)
    if not clean and old is not None:
        return record_id  # type: ignore[return-value]
    try:
        with db.connect() as conn:
            if old is None:
                cols = list(clean)
                cur = conn.execute(
                    f"INSERT INTO {rt.key} ({', '.join(cols)}) "
                    f"VALUES ({', '.join('?' for _ in cols)})", [clean[c] for c in cols])
                record_id = int(cur.lastrowid)
            else:
                sets = ", ".join(f"{c} = ?" for c in clean)
                conn.execute(f"UPDATE {rt.key} SET {sets}, updated_at = datetime('now') "
                             f"WHERE id = ?", [*clean.values(), record_id])
            row = dict(conn.execute(f"SELECT * FROM {rt.key} WHERE id = ?",
                                    (record_id,)).fetchone())
            if rt.after_save is not None:
                rt.after_save(conn, row, old)
            _log(conn, rt, row, "updated" if old else "added", actor, old)
    except db.IntegrityError as exc:
        raise ValidationError(_integrity_message(rt, exc)) from None
    if rt.after_commit is not None:
        _run_after_commit(rt, row, old)
    return record_id  # type: ignore[return-value]


#: Lines for the person who saved: what an ``after_commit`` hook did or
#: couldn't do. The form / menu shows them after the save.
_NOTICES: list[str] = []


def _run_after_commit(rt: RecordType, row: dict, old: dict | None) -> None:
    try:
        _NOTICES.extend(rt.after_commit(row, old) or [])
    except Exception as exc:  # noqa: BLE001 - the save stands; say what didn't happen
        logger.exception("after_commit for %s #%s failed", rt.key, row.get("id"))
        _NOTICES.append(f"Saved, but the platform wasn't updated: {exc}")


def take_notices() -> list[str]:
    """The notices since the last call (and clear them)."""
    out = list(_NOTICES)
    _NOTICES.clear()
    return out


def delete(rt: RecordType, record_id: int, *, actor: str = "system") -> None:
    """Delete a record; refused (ValidationError) while other records use it."""
    row = get(rt, record_id)
    if row is None:
        return
    try:
        with db.connect() as conn:
            conn.execute(f"DELETE FROM {rt.key} WHERE id = ?", (record_id,))
            _log(conn, rt, row, "deleted", actor, None)
    except db.IntegrityError:
        raise ValidationError(
            f"This {rt.singular} can't be deleted because other records still refer to it."
            + (" Archive the child instead." if rt.key == "learners" else
               " Delete or move those first.")) from None


def _integrity_message(rt: RecordType, exc: Exception) -> str:
    text = str(exc)
    if "UNIQUE" in text:
        col = text.rsplit(".", 1)[-1]
        label = rt.fields_by_name[col].label if col in rt.fields_by_name else col
        return f"Another {rt.singular} already has that {label}."
    if "FOREIGN KEY" in text:
        return "A linked record it points at no longer exists."
    return f"The {rt.singular} couldn't be saved ({text})."


# ── history / chronology ─────────────────────────────────────────────

db.register_schema("history", """
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL DEFAULT (datetime('now')),
  actor TEXT NOT NULL,
  record_type TEXT NOT NULL,
  record_id INTEGER NOT NULL,
  learner_id INTEGER,          -- no FK: the history outlives a deleted record
  action TEXT NOT NULL,
  summary TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_history_learner ON history(learner_id, at);
""")


def _changed(rt: RecordType, row: dict, old: dict | None) -> str:
    if old is None:
        return ""
    names = [f.label for f in rt.fields if old.get(f.name) != row.get(f.name)]
    return f" ({', '.join(names)})" if names else ""


def _log(conn: sqlite3.Connection, rt: RecordType, row: dict, action: str,
         actor: str, old: dict | None) -> None:
    lf = rt.learner_field
    learner_id = row["id"] if rt.key == "learners" else (row.get(lf.name) if lf else None)
    summary = f"{rt.singular.capitalize()} {action}: {rt.label_for(row)}{_changed(rt, row, old)}"
    conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, action, summary)"
                 " VALUES (?, ?, ?, ?, ?, ?)",
                 (actor, rt.key, row["id"], learner_id, action, summary[:500]))


def history(*, learner_id: int | None = None, limit: int = 200) -> list[dict]:
    sql, args = "SELECT * FROM history", []
    if learner_id is not None:
        sql += " WHERE learner_id = ?"
        args.append(learner_id)
    sql += " ORDER BY at DESC, id DESC LIMIT ?"
    args.append(limit)
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def fmt(f: Field, value: Any) -> str:
    """A stored value as shown in a list (dates as DD/MM/YYYY, money as £)."""
    if value in (None, ""):
        return ""
    if f.kind == "date":
        try:
            return date.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return str(value)
    if f.kind == "money":
        return f"£{float(value):,.2f}"
    if f.kind == "number":
        return f"{float(value):g}"
    if f.kind == "bool":
        return "Yes" if value else "No"
    if f.kind == "long":
        text = str(value).replace("\n", " ")
        return text if len(text) <= 60 else text[:57] + "…"
    return str(value)


def all_types() -> Iterable[RecordType]:
    return REGISTRY.values()
