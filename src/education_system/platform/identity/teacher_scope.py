"""Limit a teacher to their own classes, for a school system's GUI and CLI.

Each system states who a teacher teaches and what they may change in
``systems/<system>/domain/teacher_scope.py``; this module holds the mechanics.

Reading. While a teacher's session is active on the main thread, a connection
opened through :func:`connect` hides other classes' rows: each pupil-linked table
is shadowed by a TEMP view of the same name, so every domain query, including
summaries and report joins, sees only that teacher's pupils. Domain code does not
change. Nothing happens outside an active session: API, schedulers, background
threads, admins and tests get a plain connection and whole-school data.

Writing. A shadowed table is a view, so SQLite refuses every write to it. That is
the default: a write nobody has thought about fails closed. A write reaches the
table only through :func:`SystemScope.guard`, which checks the rule for that
domain function and then runs it unshadowed. Screens wrap their domain module
with ``guard`` to get that check and a clear refusal message.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Mapping

logger = logging.getLogger(__name__)

#: How long a resolved scope is used before the link tables are read again.
SCOPE_TTL_SECONDS = 30.0

OWN_PUPILS_ONLY = "You can only change records for pupils in your own classes."
READ_ONLY = ("Teacher accounts can view this but not change it. "
             "Please ask the school office.")
ADMIN_TASK = ("This is an administrator task, so it is not available to teacher "
              "accounts. Please ask the school office.")

_PUPIL_COLUMNS = ("pupil_id", "student_id")
_PUPIL_KEYS = ("pupil_id", "student_id", "mentee_id", "mentor_id")
_DDL_HEADS = {"CREATE", "ALTER", "DROP", "REINDEX"}
_DDL_ERRORS = ("may not be indexed", "column to a view", "may not be altered",
               "use DROP VIEW", "views may not")


class ScopeDenied(Exception):
    """A teacher tried to do something their limit does not allow."""


def norm(value: Any) -> str:
    """How two names or e-mails are compared: ignoring case and extra spaces."""
    return " ".join(str(value or "").split()).casefold()


@dataclass(frozen=True)
class TeacherScope:
    """Who one teacher is and which pupils they teach, right now."""

    matched: bool = False
    staff_id: str | None = None
    staff_name: str = ""
    #: Every normalised way this teacher is written in the free-text columns.
    identities: frozenset[str] = frozenset()
    #: ``(year_group, form_or_class)``, in display form.
    classes: frozenset[tuple[str, str]] = frozenset()
    pupil_ids: frozenset[str] = frozenset()
    is_dsl: bool = False
    #: Teaching groups that came from pupils' option choices, for display.
    groups: frozenset[str] = frozenset()

    @property
    def is_empty(self) -> bool:
        return not self.pupil_ids and not self.classes

    def allows_pupil(self, pupil_id: Any) -> bool:
        return str(pupil_id or "").strip() in self.pupil_ids

    def allows_class(self, year_group: Any, name: Any) -> bool:
        wanted = (norm(year_group), norm(name))
        return any((norm(y), norm(n)) == wanted for y, n in self.classes)

    def class_summary(self) -> str:
        labels = sorted(f"{y} {n}" for y, n in self.classes) + sorted(self.groups)
        return ", ".join(labels)


# ── Session state: one per thread, so background threads are never limited ───

class _State(threading.local):
    source: Callable[[], TeacherScope] | None = None
    config: "SystemScope | None" = None
    scope: TeacherScope | None = None
    resolved_at: float = 0.0
    suspended: int = 0
    connections: dict[str, "ScopedConnection"]

    def __init__(self) -> None:
        self.connections = {}


_state = _State()


def _resolve_now() -> TeacherScope:
    """The session's scope, re-read when stale. Any failure means no pupils."""
    now = time.monotonic()
    if _state.scope is not None and now - _state.resolved_at < SCOPE_TTL_SECONDS:
        return _state.scope
    with suspended():
        try:
            scope = _state.source() if _state.source else TeacherScope()
        except Exception:
            logger.exception("Could not work out this teacher's classes")
            scope = TeacherScope()
    _state.scope = scope
    _state.resolved_at = now
    return scope


def current() -> TeacherScope | None:
    """The active teacher's scope on this thread, or None if nobody is limited."""
    if _state.source is None or _state.suspended:
        return None
    return _resolve_now()


def activate(config: "SystemScope", source: Callable[[], TeacherScope]) -> None:
    """Start limiting this thread. ``source`` is read lazily, on first use."""
    end_session()
    _state.config = config
    _state.source = source


def end_session() -> None:
    """Stop limiting this thread and close its limited connections."""
    for conn in _state.connections.values():
        conn.really_close()
    _state.connections = {}
    _state.config = None
    _state.source = None
    _state.scope = None
    _state.resolved_at = 0.0
    _state.suspended = 0


def refresh() -> None:
    """Drop the cached scope, so the next read sees current class links."""
    _state.scope = None


@contextlib.contextmanager
def suspended() -> Iterator[None]:
    """Run a checked write, or housekeeping that reveals nothing, unshadowed."""
    _state.suspended += 1
    try:
        yield
    finally:
        _state.suspended -= 1


def connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
    """``sqlite3.connect``, limited to the active teacher when there is one."""
    config = _state.config
    if (config is None or _state.source is None or _state.suspended
            or str(database) != str(config.db_path())):
        return sqlite3.connect(database, *args, **kwargs)
    return _scoped_connection(str(database), config)


def _scoped_connection(path: str, config: "SystemScope") -> "ScopedConnection":
    scope = _resolve_now()
    conn = _state.connections.get(path)
    if conn is None:
        conn = sqlite3.connect(path, factory=ScopedConnection)
        conn.setup(path, config)
        _state.connections[path] = conn
    conn.apply(scope)
    conn.row_factory = None
    return conn


# ── The limited connection ───────────────────────────────────────────────────

def _head(sql: str) -> str:
    match = re.match(r"\s*(\w+)", sql)
    return match.group(1).upper() if match else ""


class ScopedCursor(sqlite3.Cursor):
    def execute(self, sql, *params):  # type: ignore[override]
        return self.connection._guarded(super().execute, sql, *params)

    def executemany(self, sql, *params):  # type: ignore[override]
        return self.connection._guarded(super().executemany, sql, *params)

    def executescript(self, script):  # type: ignore[override]
        self.connection._forward(script)
        return self


class ScopedConnection(sqlite3.Connection):
    """A connection with other classes' rows hidden.

    One is kept per database for the session, because building the views costs
    more than opening a connection and domain code opens one per call. ``close``
    therefore does nothing until the session ends.
    """

    _path: str
    _config: "SystemScope"
    _applied: TeacherScope | None = None
    _views: frozenset[str] = frozenset()

    def setup(self, path: str, config: "SystemScope") -> None:
        self._path = path
        self._config = config
        sqlite3.Connection.execute(self, "PRAGMA temp_store=MEMORY")
        sqlite3.Connection.executescript(self, """
            CREATE TEMP TABLE IF NOT EXISTS _scope_pupils (id TEXT PRIMARY KEY);
            CREATE TEMP TABLE IF NOT EXISTS _scope_classes (
                year_group TEXT, name TEXT);
            CREATE TEMP TABLE IF NOT EXISTS _scope_names (name TEXT PRIMARY KEY);
        """)

    def apply(self, scope: TeacherScope) -> None:
        if scope is not self._applied:
            self._fill(scope)
            self._build_views(scope)
            self._applied = scope

    def _fill(self, scope: TeacherScope) -> None:
        raw = sqlite3.Connection
        raw.execute(self, "DELETE FROM temp._scope_pupils")
        raw.execute(self, "DELETE FROM temp._scope_classes")
        raw.execute(self, "DELETE FROM temp._scope_names")
        raw.executemany(self, "INSERT OR IGNORE INTO temp._scope_pupils VALUES (?)",
                        [(p,) for p in scope.pupil_ids])
        raw.executemany(self, "INSERT INTO temp._scope_classes VALUES (?, ?)",
                        [(norm(y), norm(n)) for y, n in scope.classes])
        raw.executemany(self, "INSERT OR IGNORE INTO temp._scope_names VALUES (?)",
                        [(n,) for n in scope.identities])
        raw.commit(self)

    def _build_views(self, scope: TeacherScope) -> None:
        raw = sqlite3.Connection
        plan = self._config.view_plan(self, scope)
        statements = [f'DROP VIEW IF EXISTS temp."{t}"' for t in self._views]
        statements += [
            f'CREATE TEMP VIEW "{table}" AS SELECT * FROM main."{table}" '
            f"WHERE {predicate}"
            for table, predicate in plan.items()]
        raw.executescript(self, "BEGIN;" + ";".join(statements) + ";COMMIT;")
        self._views = frozenset(plan)

    def _forward(self, sql: str, *params: Any) -> None:
        """Schema statements from a module's ``init_db`` go to the real tables."""
        plain = sqlite3.connect(self._path)
        try:
            if params:
                plain.execute(sql, *params)
            else:
                plain.executescript(sql)
            plain.commit()
        finally:
            plain.close()
        if self._applied is not None:
            self._build_views(self._applied)

    def _guarded(self, run: Callable[..., Any], sql: str, *params: Any) -> Any:
        if _head(sql) in _DDL_HEADS:
            self._forward(sql, *params)
            return self.cursor()
        try:
            return run(sql, *params)
        except sqlite3.OperationalError as exc:
            message = str(exc)
            if "because it is a view" in message:
                table = message.split("modify", 1)[-1].split()[0] if (
                    "modify" in message) else ""
                raise ScopeDenied(self._config.refusal_for_table(table)) from exc
            if any(text in message for text in _DDL_ERRORS):
                self._forward(sql, *params)
                return self.cursor()
            raise

    def execute(self, sql, *params):  # type: ignore[override]
        return self._guarded(super().execute, sql, *params)

    def executemany(self, sql, *params):  # type: ignore[override]
        return self._guarded(super().executemany, sql, *params)

    def executescript(self, script):  # type: ignore[override]
        self._forward(script)
        return self.cursor()

    def cursor(self, factory=ScopedCursor):  # type: ignore[override]
        return super().cursor(factory)

    def close(self) -> None:  # type: ignore[override]
        """Kept open for the session; :meth:`really_close` ends it."""

    def really_close(self) -> None:
        sqlite3.Connection.close(self)


# ── Rules: what each domain function needs before it may write ───────────────

@dataclass(frozen=True)
class Rule:
    kind: str
    table: str | None = None
    key: str | None = None
    message: str | None = None
    check: Callable[[TeacherScope, Mapping[str, Any]], None] | None = None


def pupil() -> Rule:
    """The call must name a pupil, in an argument or its payload, in scope."""
    return Rule("pupil")


def pupil_if_named() -> Rule:
    """If the call names a pupil they must be in scope; it need not name one."""
    return Rule("pupil_if_named")


def row(table: str) -> Rule:
    """The first argument is a key of ``table``, and that row must be visible."""
    return Rule("row", table=table)


def parent(table: str, key: str) -> Rule:
    """The payload's ``key`` must be a visible row of ``table``."""
    return Rule("parent", table=table, key=key)


def own_class() -> Rule:
    """The payload's year group and form must be one of the teacher's classes."""
    return Rule("own_class")


def matched() -> Rule:
    """Any pupil, but the login must match a staff record."""
    return Rule("matched")


def anyone() -> Rule:
    """No limit: the write shows nothing back, such as raising a concern."""
    return Rule("anyone")


def deny(message: str = ADMIN_TASK) -> Rule:
    return Rule("deny", message=message)


def custom(check: Callable[[TeacherScope, Mapping[str, Any]], None]) -> Rule:
    """``check(scope, arguments)`` raises :class:`ScopeDenied` to refuse."""
    return Rule("custom", check=check)


def rules_for(rule: Rule, *names: str) -> dict[str, Rule]:
    return {name: rule for name in names}


def _pupil_refs(arguments: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key, value in arguments.items():
        if key in _PUPIL_KEYS and value not in (None, ""):
            refs.append(str(value).strip())
        elif isinstance(value, Mapping):
            refs.extend(str(value[k]).strip() for k in _PUPIL_KEYS
                        if value.get(k) not in (None, ""))
    return refs


def _payloads(arguments: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    return (v for v in arguments.values() if isinstance(v, Mapping))


# ── A system's configuration, and the guard its screens use ──────────────────

@dataclass
class SystemScope:
    """The parts of the limit one school system has to state."""

    db_path: Callable[[], Any]
    #: Table → SQL predicate, for tables not limited by a pupil column.
    table_predicates: Callable[[TeacherScope], Mapping[str, str]]
    #: Every row visible but no writes: the links the limit itself rests on,
    #: and whole-school records with no link to a class.
    read_only_tables: frozenset[str]
    #: Safeguarding records. Hidden unless the teacher is a safeguarding lead,
    #: who sees them all.
    lead_only_tables: frozenset[str]
    #: Pupil-linked tables an uninvolved row may have no pupil on.
    optional_pupil_tables: frozenset[str] = frozenset()
    #: Domain module short name → function name → rule.
    rules: Mapping[str, Mapping[str, Rule]] = field(default_factory=dict)
    #: Domain modules a safeguarding lead uses whole-school.
    lead_modules: frozenset[str] = frozenset()

    # View planning ------------------------------------------------------

    def view_plan(self, conn: sqlite3.Connection,
                  scope: TeacherScope) -> dict[str, str]:
        raw = sqlite3.Connection.execute
        tables = [r[0] for r in raw(conn,
            "SELECT name FROM main.sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        columns = {t: {r[1] for r in raw(conn, f'PRAGMA main.table_info("{t}")').fetchall()}
                   for t in tables}
        pupils = "(SELECT id FROM temp._scope_pupils)"
        plan: dict[str, str] = {}
        limited: set[str] = set()
        custom_predicates = dict(self.table_predicates(scope))
        for table in tables:
            if table in self.lead_only_tables:
                if scope.is_dsl:
                    continue
                plan[table] = "0"
                limited.add(table)
            elif table in custom_predicates:
                plan[table] = custom_predicates[table]
                limited.add(table)
            elif table in self.read_only_tables:
                plan[table] = "1"
            else:
                column = next((c for c in _PUPIL_COLUMNS if c in columns[table]), None)
                if column:
                    predicate = f'"{column}" IN {pupils}'
                    if table in self.optional_pupil_tables:
                        predicate = f'("{column}" IS NULL OR {predicate})'
                    plan[table] = predicate
                    limited.add(table)
        # Child rows, such as reviews of a SEND record, follow their parent.
        changed = True
        while changed:
            changed = False
            for table in tables:
                if table in plan or (table in self.lead_only_tables and scope.is_dsl):
                    continue
                for fk in raw(conn, f'PRAGMA main.foreign_key_list("{table}")').fetchall():
                    parent_table, col, parent_col = fk[2], fk[3], fk[4]
                    if parent_table in limited:
                        plan[table] = (f'"{col}" IN (SELECT "{parent_col}" '
                                       f'FROM temp."{parent_table}")')
                        limited.add(table)
                        changed = True
                        break
        # A view may only read a view that already exists: parents first.
        return dict(sorted(plan.items(),
                           key=lambda kv: "temp." in kv[1].replace("temp._scope", "")))

    def refusal_for_table(self, table: str) -> str:
        if table in self.read_only_tables:
            return READ_ONLY
        return OWN_PUPILS_ONLY

    # Guarding -----------------------------------------------------------

    def guard(self, module: Any) -> "GuardedModule":
        return GuardedModule(module, self)

    def row_visible(self, table: str, key: Any) -> bool:
        conn = connect(self.db_path())
        info = sqlite3.Connection.execute(
            conn, f'PRAGMA main.table_info("{table}")').fetchall()
        pk = next((r[1] for r in info if r[5]), None)
        if pk is None:
            return False
        found = sqlite3.Connection.execute(
            conn, f'SELECT 1 FROM "{table}" WHERE "{pk}" = ?', (key,)).fetchone()
        return found is not None


class GuardedModule:
    """A domain module whose functions apply the active teacher's limit.

    For admins and anyone else outside a teacher session each function behaves
    exactly as the module's own. Everything that is not a function passes through.
    """

    def __init__(self, module: Any, config: SystemScope) -> None:
        self._module = module
        self._config = config
        self._short = module.__name__.rsplit(".", 1)[-1]
        self._rules = config.rules.get(self._short, {})
        self._is_lead_module = self._short in config.lead_modules

    def __repr__(self) -> str:
        return f"<guarded {self._module.__name__}>"

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._module, name)
        if (name.startswith("_") or not callable(attr) or inspect.isclass(attr)):
            return attr
        wrapped = self._wrap(name, attr)
        self.__dict__[name] = wrapped
        return wrapped

    def _refuse(self, message: str) -> ScopeDenied:
        """A refusal the screen's own ``except ValidationError`` also catches."""
        base = getattr(self._module, "ValidationError", None)
        if inspect.isclass(base) and issubclass(base, Exception):
            return type("ScopeDenied", (ScopeDenied, base), {})(message)
        return ScopeDenied(message)

    def _wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        rule = self._rules.get(name)

        @functools.wraps(fn)
        def call(*args: Any, **kwargs: Any) -> Any:
            scope = current()
            if scope is None:
                return fn(*args, **kwargs)
            if self._is_lead_module and scope.is_dsl:
                with suspended():
                    return fn(*args, **kwargs)
            if rule is None:
                return fn(*args, **kwargs)
            self._check(scope, rule, fn, args, kwargs)
            with suspended():
                return fn(*args, **kwargs)
        return call

    def _check(self, scope: TeacherScope, rule: Rule, fn: Callable[..., Any],
               args: tuple, kwargs: dict) -> None:
        if rule.kind == "deny":
            raise self._refuse(rule.message or ADMIN_TASK)
        if rule.kind == "anyone":
            return
        if rule.kind == "matched":
            if not scope.matched:
                raise self._refuse(self._config_unmatched(scope))
            return
        try:
            arguments = inspect.signature(fn).bind(*args, **kwargs).arguments
        except TypeError:
            arguments = {}
        refs = _pupil_refs(arguments)
        if rule.kind == "pupil" and not refs:
            raise self._refuse("Please name a pupil from your own classes.")
        if any(not scope.allows_pupil(p) for p in refs):
            raise self._refuse(OWN_PUPILS_ONLY)
        if rule.kind == "row":
            key = next(iter(arguments.values()), None)
            if not self._config.row_visible(rule.table or "", key):
                raise self._refuse(OWN_PUPILS_ONLY)
        elif rule.kind == "parent":
            key = next((p.get(rule.key) for p in _payloads(arguments)
                        if p.get(rule.key) not in (None, "")), None)
            if key is None or not self._config.row_visible(rule.table or "", key):
                raise self._refuse(OWN_PUPILS_ONLY)
        elif rule.kind == "own_class":
            for payload in _payloads(arguments):
                if not scope.allows_class(payload.get("year_group"),
                                          payload.get("form_group")):
                    raise self._refuse("Please choose one of your own classes.")
        elif rule.kind == "custom" and rule.check is not None:
            try:
                rule.check(scope, arguments)
            except ScopeDenied as exc:
                raise self._refuse(str(exc)) from exc

    @staticmethod
    def _config_unmatched(_scope: TeacherScope) -> str:
        return ("Your login is not linked to a staff record, so this cannot be "
                "saved. Please ask the school office to check your staff record.")


def install_tk_refusal(root: Any) -> None:
    """Show a refusal no screen caught as a message, not a stack trace."""
    previous = root.report_callback_exception

    def report(exc_type, exc, tb):
        if isinstance(exc, ScopeDenied):
            from tkinter import messagebox
            logger.info("Refused: %s", exc)
            messagebox.showerror("Not available", str(exc), parent=root)
            return
        previous(exc_type, exc, tb)

    root.report_callback_exception = report


# ── Common rules, for domain modules both school systems share ───────────────

def _class_fields_stay_in_scope(fields: tuple[str, ...]) -> Callable[..., None]:
    """Refuse moving a pupil out to, or in from, a class the teacher lacks."""
    def check(scope: TeacherScope, arguments: Mapping[str, Any]) -> None:
        if not scope.allows_pupil(arguments.get("pupil_id")):
            raise ScopeDenied(OWN_PUPILS_ONLY)
        for payload in _payloads(arguments):
            if any(key in payload for key in fields):
                raise ScopeDenied(
                    "Only an administrator can move a pupil to another class "
                    "or year group.")
    return check


def _marks_in_scope(scope: TeacherScope, arguments: Mapping[str, Any]) -> None:
    marks = arguments.get("marks") or {}
    if any(not scope.allows_pupil(pid) for pid in marks):
        raise ScopeDenied(OWN_PUPILS_ONLY)


def _bulk_message_in_scope(scope: TeacherScope, arguments: Mapping[str, Any]) -> None:
    kwargs = arguments.get("kwargs") or {}
    ids = list(arguments.get("student_ids") or kwargs.get("student_ids") or [])
    if any(not scope.allows_pupil(pid) for pid in ids):
        raise ScopeDenied(OWN_PUPILS_ONLY)


def _own_rows(table: str, *names: str) -> dict[str, Rule]:
    return rules_for(row(table), *names)


def _standard(table: str, create: str = "create", update: str = "update",
              delete: str = "delete", extra: Iterable[str] = ()) -> dict[str, Rule]:
    """A pupil's record: add for an own pupil, change only rows they can see."""
    rules = {create: pupil(), update: row(table), delete: row(table)}
    rules.update(rules_for(row(table), *extra))
    return rules


def _all_denied(*names: str, message: str = ADMIN_TASK) -> dict[str, Rule]:
    return rules_for(deny(message), *names)


COMMON_RULES: dict[str, dict[str, Rule]] = {
    # ── Attendance ───────────────────────────────────────────────────────
    "attendance": {
        "record_mark": pupil(),
        "bulk_record": custom(_marks_in_scope),
        "delete_record": row("attendance_records"),
    },
    "attendance_concerns": _standard(
        "attendance_concerns", extra=("set_status", "close")),
    "absence_requests": _standard(
        "absence_requests", extra=("decide", "cancel")),
    # ── Homework and coursework ──────────────────────────────────────────
    "homework": {
        "create_assignment": own_class(),
        "update_assignment": row("homework_assignments"),
        "set_assignment_status": row("homework_assignments"),
        "delete_assignment": row("homework_assignments"),
        "seed_submissions": row("homework_assignments"),
        "upsert_submission": row("homework_assignments"),
        "delete_submission": row("homework_submissions"),
    },
    # ── Assessment ───────────────────────────────────────────────────────
    "early_warning": _standard(
        "early_warning_alerts", extra=("resolve", "dismiss", "set_status")),
    "intervention_tracking": {
        **_standard("interventions", extra=("set_status",)),
        "add_review": parent("interventions", "intervention_id"),
        "delete_review": row("intervention_reviews"),
    },
    # ── Behaviour and pastoral care ──────────────────────────────────────
    "behaviour": _standard(
        "behaviour_incidents", create="log_incident", extra=("set_status",)),
    "accessibility": _standard(
        "accessibility_arrangements", extra=("set_status",)),
    "wellbeing": _standard(
        "wellbeing_checkins", create="log_checkin", extra=("set_status",)),
    "pupil_support": {
        **_standard("support_plans", create="create_plan", update="update_plan",
                    delete="delete_plan", extra=("set_status",)),
        "add_review": parent("support_plans", "plan_id"),
        "delete_review": row("support_plan_reviews"),
    },
    "send": {
        "upsert": pupil(),
        "delete": row("send_records"),
        "add_review": parent("send_records", "send_id"),
        "delete_review": row("send_reviews"),
    },
    "pupil_premium": {
        "upsert": pupil(),
        "delete": row("pupil_premium_records"),
        "add_intervention": parent("pupil_premium_records", "pp_id"),
        "update_intervention": row("pp_interventions"),
        "delete_intervention": row("pp_interventions"),
    },
    "first_aid": _standard("first_aid_incidents"),
    "medical_records": _standard("medical_records", extra=("toggle_active",)),
    "school_council": {
        "create_member": pupil(),
        "update_member": row("school_council_members"),
        "delete_member": row("school_council_members"),
        "end_term": row("school_council_members"),
        "set_member_status": row("school_council_members"),
    },
    "transport": {
        "create_arrangement": pupil(),
        **_own_rows(
            "transport_arrangements", "update_arrangement", "delete_arrangement",
            "activate", "suspend", "end_arrangement", "cancel", "set_fee_status",
            "set_arrangement_status"),
    },
    "health_safety": {},
    # ── Pupil records ────────────────────────────────────────────────────
    "pupils": {
        "create_pupil": deny(
            "New pupils are added by the school office, so this is not available "
            "to teacher accounts."),
        "set_roll_status": deny(),
        "delete_pupil": deny(),
        "update_pupil": custom(_class_fields_stay_in_scope(
            ("year_group", "class_name", "form_group"))),
    },
    "onboarding": {"set_step": pupil(), "mark_all": pupil()},
    "bulk_operations": _all_denied("import_pupils_csv", "bulk_update", "bulk_delete"),
    "enrolment": _all_denied("move_pupil", "promote_year"),
    "admissions": _all_denied(
        "create_application", "update_application", "set_status",
        "enrol_application", "delete_application"),
    # ── Communication about a pupil ──────────────────────────────────────
    "parent_contacts": {
        "create_contact": pupil(),
        "update_contact": row("parent_contacts"),
        "set_primary": row("parent_contacts"),
        "delete_contact": row("parent_contacts"),
    },
    "parents_evenings": {
        "create_booking": pupil(),
        "update_booking": row("parents_evening_bookings"),
        "set_booking_status": row("parents_evening_bookings"),
        "delete_booking": row("parents_evening_bookings"),
    },
    "messages": {
        "create_message": pupil_if_named(),
        "reply": row("messages"),
        "update_message": row("messages"),
        "send_message": row("messages"),
        "mark_failed": row("messages"),
        "set_status": row("messages"),
        "delete_message": row("messages"),
        "bulk_send": custom(_bulk_message_in_scope),
    },
    # ── No class to link to, so a teacher sees only their own ────────────
    "complaints": {
        "create_complaint": anyone(),
        **_own_rows(
            "complaints", "update_complaint", "delete_complaint", "acknowledge",
            "start_investigation", "issue_response", "escalate",
            "record_satisfaction", "close_complaint", "set_status"),
    },
    "feedback": {
        "create_feedback": anyone(),
        **_own_rows(
            "feedback", "update_feedback", "delete_feedback", "assign", "respond",
            "mark_acted", "close_feedback", "archive", "set_status"),
    },
    "equality_diversity": {
        "create_incident": anyone(),
        **_own_rows(
            "ed_incidents", "update_incident", "delete_incident",
            "start_investigation", "record_outcome", "set_actions", "resolve",
            "close_incident", "set_status"),
    },
    # ── No class to link to and whole-school: read-only ──────────────────
    "emergency": _all_denied(
        "create", "update", "set_status", "close_event", "delete", message=READ_ONLY),
    "surveys": {
        **_all_denied(
            "create_survey", "update_survey", "delete_survey", "publish",
            "close_survey", "archive", "set_status", "delete_response",
            message=READ_ONLY),
        # A teacher can still answer a survey.
        "submit_response": anyone(),
    },
    # ── The links the limit rests on: read-only, or a teacher could add a
    #    class to their own list, or set the safeguarding flag on themselves ─
    "staff": _all_denied(
        "create_staff", "update_staff", "mark_left", "delete_staff",
        message=READ_ONLY),
    "timetable": _all_denied(
        "create_slot", "update_slot", "delete_slot", message=READ_ONLY),
    "cover": _all_denied(
        "create", "update", "assign", "set_status", "delete", message=READ_ONLY),
    "year_groups": _all_denied("upsert", "delete", message=READ_ONLY),
    # ── Leaving the school ───────────────────────────────────────────────
    "secondary_transfer": _all_denied("move_to_secondary_school"),
    # ── Safeguarding: anyone raises, only a lead does more ───────────────
    "safeguarding": {
        "raise_concern": anyone(),
        **_all_denied(
            "update", "set_status", "delete", "add_action", "delete_action",
            message="Only a designated safeguarding lead can do this."),
    },
    "prevent_duty": _all_denied(
        "create", "update", "set_status", "close_referral", "delete",
        message="Only a designated safeguarding lead can do this."),
}

#: Tables every system treats the same way.
COMMON_READ_ONLY_TABLES = frozenset({
    "staff", "timetable_slots", "cover_arrangements", "year_groups",
    "emergency_events", "surveys", "survey_responses",
})
LEAD_ONLY_TABLES = frozenset({
    "safeguarding_concerns", "safeguarding_actions", "prevent_referrals",
})
LEAD_MODULES = frozenset({"safeguarding", "prevent_duty"})
#: A message, first-aid entry or health-and-safety incident may involve no pupil.
OPTIONAL_PUPIL_TABLES = frozenset({"messages", "first_aid_incidents"})


def own_row_predicates(_scope: TeacherScope) -> dict[str, str]:
    """Whole-school records naming no pupil: a teacher sees those they run."""
    names = "(SELECT name FROM temp._scope_names)"

    def mine(*columns: str) -> str:
        return " OR ".join(f'lower(trim("{c}")) IN {names}' for c in columns)

    return {
        "complaints": mine("assigned_to"),
        "feedback": mine("assigned_to"),
        "ed_incidents": mine("reporter", "investigated_by"),
        "hs_incidents": (
            '"affected_student_id" IS NULL OR "affected_student_id" IN '
            "(SELECT id FROM temp._scope_pupils)"),
    }


def homework_predicate(table: str = "homework_assignments") -> str:
    """Own class, set by this teacher, or a year-wide task for an own year."""
    names = "(SELECT name FROM temp._scope_names)"
    classes = ("EXISTS (SELECT 1 FROM temp._scope_classes c WHERE "
               f'c.year_group = lower(trim("{table}"."year_group")) AND '
               f'c.name = lower(trim("{table}"."form_group")))')
    year_wide = (f'(trim(coalesce("{table}"."form_group", \'\')) = \'\' AND EXISTS ('
                 "SELECT 1 FROM temp._scope_classes c WHERE "
                 f'c.year_group = lower(trim("{table}"."year_group"))))')
    return f'lower(trim("set_by")) IN {names} OR {classes} OR {year_wide}'


def name_forms(staff: Any, everyone: Iterable[Any]) -> frozenset[str]:
    """How a staff member may be written in a free-text teacher column.

    Staff id, e-mail and full name, with or without a title. "Mrs Smith" counts
    only if nobody else on the staff could be meant by it.
    """
    first = getattr(staff, "first_name", "") or ""
    last = getattr(staff, "last_name", "") or ""
    title = getattr(staff, "title", "") or ""
    forms = {norm(staff.staff_id), norm(getattr(staff, "email", "")),
             norm(f"{first} {last}"), norm(f"{title} {first} {last}")}
    if title:
        same = [s for s in everyone
                if norm(getattr(s, "last_name", "")) == norm(last)
                and norm(getattr(s, "title", "")) == norm(title)]
        if len(same) == 1:
            forms.add(norm(f"{title} {last}"))
    forms.discard("")
    return frozenset(forms)


def screen_notice(scope: TeacherScope | None, *, label: str,
                  limited_labels: frozenset[str], no_pupils_open: frozenset[str],
                  unlimitable_labels: frozenset[str], read_only_labels: frozenset[str],
                  school_office: str) -> tuple[bool, str]:
    """``(blocked, message)`` for a teacher opening a menu entry.

    ``no_pupils_open`` screens open anyway with an empty list, because they can
    still do something useful without one.
    """
    if scope is None:
        return False, ""
    if label in unlimitable_labels:
        return True, (
            f"{label} shows whole-school data that cannot be limited to your "
            f"classes, so it is not available to teacher accounts. "
            f"Please ask {school_office}.")
    if label not in limited_labels:
        note = (READ_ONLY if label in read_only_labels else "")
        return False, note
    if not scope.matched:
        message = (
            f"We could not link your login to a staff record, so {label} shows "
            f"no pupils. Please ask {school_office} to check that your username "
            "or e-mail is on your staff record.")
        return (label not in no_pupils_open or True), message
    if scope.is_empty:
        message = (
            f"Your staff record is not linked to any class yet, so {label} has "
            f"no pupils to show. Please ask {school_office} to add you as a "
            "class teacher or tutor, or on the timetable.")
        return (label not in no_pupils_open), message
    note = f"Showing your classes only: {scope.class_summary()}."
    if label in read_only_labels:
        note += f" {READ_ONLY}"
    return False, note
