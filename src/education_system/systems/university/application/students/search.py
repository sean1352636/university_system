"""Advanced student search: one rule set behind the Advanced Search window,
its CLI menu, exports, bulk actions and scheduled reports.

* **Criteria** are ``{"match": "all"|"any", "conditions": [{field, op,
  value}], "text": "free text", "all_fields": bool}``. Every field comes
  from :data:`FIELDS` and every value is a bound parameter - no user text
  ever becomes SQL. Text conditions also take a wildcard pattern (``*`` and
  ``?``), a regular expression (checked, at most 200 characters, run by a
  ``REGEXP`` function registered on the connection) and "sounds like"
  (similar spelling or the same Soundex code). With ``all_fields`` the free
  text is looked for in every text field the viewer may see, not only ID,
  name, email and course.
* **Data** follows the current model: course by code *or* name (students
  are filed under either), the lifecycle statuses (legacy 'Graduated' counts
  as Completed), marks from ``module_grades``, attendance from
  ``attendance_records``, enrolments from ``student_modules``. Erased
  records (``ERASED-...``) never appear.
* **Who sees what** (:class:`Viewer`): staff with ``view_any_student`` see
  every student, anyone else only themselves; personal fields (date of
  birth, contact details, nationality) only for admins.
* **Audit**: every search and export is recorded
  (``student_search_audit``); callers commit.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher

from education_system.systems.university.infrastructure.database.schemas import (
    student_search_schema as schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
STATUSES = ("Active", "Registration Pending", "Interrupted", "Withdrawn", "Deferred",
            "Suspended", "Completed", "Closed")
PAGE_SIZES = (25, 50, 100, 250)
MAX_EXPORT = 20000
SIMILAR_RATIO = 0.75

_COURSE = ("COALESCE((SELECT COALESCE(NULLIF(c.course_code, ''), c.code) FROM courses c "
           "WHERE s.course IN (c.course_code, c.code, c.course_name, c.name) LIMIT 1), s.course)")
_STATUS = ("CASE WHEN LOWER(COALESCE(s.status, '')) = 'graduated' THEN 'Completed' "
           "ELSE s.status END")
_MARK = ("(SELECT ROUND(AVG(mg.final_score), 1) FROM module_grades mg WHERE mg.student_id = "
         "s.student_id AND mg.final_score IS NOT NULL)")
_ATTENDANCE = ("(SELECT ROUND(100.0 * SUM(LOWER(ar.status) IN ('present', 'late')) / COUNT(*), 1)"
               " FROM attendance_records ar WHERE ar.student_id = s.student_id)")
_AGE = ("CAST((julianday('now') - julianday(s.dob)) / 365.25 AS INTEGER)")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    expr: str
    kind: str                 # text | choice | number | date | module
    sensitive: bool = False
    column: bool = True       # shown as a results column


FIELDS = {f.key: f for f in (
    Field("student_id", "Student ID", "s.student_id", "text"),
    Field("name", "Name", "TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))",
          "text"),
    Field("first_name", "First name", "s.first_name", "text", column=False),
    Field("last_name", "Last name", "s.last_name", "text", column=False),
    Field("email_address", "University email", "s.email_address", "text"),
    Field("course", "Course", _COURSE, "choice"),
    Field("status", "Status", _STATUS, "choice"),
    Field("year_of_study", "Year of study", "s.year_of_study", "number"),
    Field("mode_of_study", "Mode of study", "s.mode_of_study", "choice"),
    Field("fee_status", "Fee status", "s.fee_status", "choice"),
    Field("entry_route", "Entry route", "s.entry_route", "choice", column=False),
    Field("gender", "Gender", "s.gender", "choice", column=False),
    Field("registration", "Registered", "SUBSTR(s.registration_datetime, 1, 10)", "date"),
    Field("average_mark", "Average mark", _MARK, "number"),
    Field("attendance", "Attendance %", _ATTENDANCE, "number"),
    Field("module", "Enrolled on module", "", "module", column=False),
    Field("dob", "Date of birth", "s.dob", "date", sensitive=True),
    Field("age", "Age", _AGE, "number", sensitive=True, column=False),
    Field("phone", "Phone", "s.phone", "text", sensitive=True),
    Field("personal_email", "Personal email", "s.personal_email", "text", sensitive=True),
    Field("address", "Home address", "s.address", "text", sensitive=True, column=False),
    Field("nationality", "Nationality", "s.nationality", "text", sensitive=True),
)}

OPS = {
    "text": ("contains", "equals", "starts with", "ends with", "does not contain",
             "is empty", "is not empty", "sounds like", "matches pattern", "matches regex"),
    "choice": ("is", "is not", "is one of", "is empty"),
    "number": ("=", "<", "<=", ">", ">=", "between", "is empty"),
    "date": ("on", "before", "after", "between", "is empty"),
    "module": ("has", "has not"),
}
_NO_VALUE = ("is empty", "is not empty")


@dataclass(frozen=True)
class Viewer:
    username: str
    role: str = ""
    can_view_all: bool = False
    can_view_sensitive: bool = False
    can_export: bool = False
    can_update: bool = False
    can_withdraw: bool = False
    student_id: str | None = None
    can_mark: bool = False
    can_manage_users: bool = False

    @classmethod
    def from_check(cls, username, role, check, student_id=None):
        """Build from an auth object's ``check_permission``-style callable."""
        def has(permission):
            try:
                return bool(check(permission))
            except Exception:
                return False
        admin = str(role or "").lower() in ADMIN_ROLES
        return cls(username=username or "", role=str(role or "").lower(),
                   can_view_all=admin or has("view_any_student"), can_view_sensitive=admin,
                   can_export=admin or has("export_data"),
                   can_update=admin or has("update_any_student"),
                   can_withdraw=admin or has("delete_any_student"), student_id=student_id,
                   can_mark=admin or has("enter_grades"),
                   can_manage_users=admin or has("manage_users"))


MAX_REGEX = 200


def _regexp(pattern, value):
    if value is None:
        return False
    try:
        return re.search(pattern, str(value), re.IGNORECASE) is not None
    except re.error:
        return False


def ensure(conn):
    schema.apply_to_connection(conn)
    try:
        conn.create_function("REGEXP", 2, _regexp, deterministic=True)
    except Exception:       # a connection proxy without create_function
        pass


def soundex(text) -> str:
    """The American Soundex code of the first word of ``text`` ("" if none)."""
    word = "".join(c for c in str(text or "").upper() if c.isalpha())
    if not word:
        return ""
    codes = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"),
             **dict.fromkeys("DT", "3"), "L": "4", **dict.fromkeys("MN", "5"), "R": "6"}
    out, last = word[0], codes.get(word[0], "")
    for c in word[1:]:
        code = codes.get(c, "")
        if code and code != last:
            out += code
        if c not in "HW":
            last = code
    return (out + "000")[:4]


def fields_for(viewer: Viewer) -> list[Field]:
    return [f for f in FIELDS.values() if viewer.can_view_sensitive or not f.sensitive]


def columns_for(viewer: Viewer) -> list[Field]:
    return [f for f in fields_for(viewer) if f.column]


def choices(conn, field_key) -> list[str]:
    """Values offered for a choice field."""
    if field_key == "status":
        return list(STATUSES)
    if field_key == "course":
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT COALESCE(NULLIF(course_code, ''), code) FROM courses WHERE "
            "COALESCE(NULLIF(course_code, ''), code) IS NOT NULL ORDER BY 1")]
    f = FIELDS[field_key]
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT {f.expr} FROM students s WHERE {f.expr} IS NOT NULL AND "
        f"{f.expr} <> '' ORDER BY 1")]


# ── building the query ──────────────────────────────────────────────────


def _like(value: str) -> str:
    return (str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))


def _text_clause(expr, op, value):
    patterns = {"contains": "%{}%", "starts with": "{}%", "ends with": "%{}",
                "does not contain": "%{}%"}
    if op == "equals":
        return f"LOWER(COALESCE({expr}, '')) = LOWER(?)", [value]
    if op == "matches pattern":
        pattern = _like(value).replace("*", "%").replace("?", "_")
        return f"LOWER(COALESCE({expr}, '')) LIKE LOWER(?) ESCAPE '\\'", [pattern]
    if op == "matches regex":
        if len(str(value)) > MAX_REGEX:
            raise ValueError(f"A regular expression can be at most {MAX_REGEX} characters")
        try:
            re.compile(str(value))
        except re.error as exc:
            raise ValueError(f"That is not a valid regular expression: {exc}") from None
        return f"{expr} REGEXP ?", [str(value)]
    if op in patterns:
        neg = "NOT " if op == "does not contain" else ""
        return (f"{neg}(LOWER(COALESCE({expr}, '')) LIKE LOWER(?) ESCAPE '\\')",
                [patterns[op].format(_like(value))])
    raise ValueError(f"'{op}' does not apply to text")


def _choice_clause(expr, op, value):
    if op in ("is", "is not"):
        neg = "NOT " if op == "is not" else ""
        return f"{neg}(LOWER(COALESCE({expr}, '')) = LOWER(?))", [value]
    if op == "is one of":
        values = [v.strip() for v in str(value).split(",") if v.strip()]
        if not values:
            raise ValueError("List at least one value")
        return (f"LOWER(COALESCE({expr}, '')) IN ({', '.join('LOWER(?)' for _ in values)})",
                values)
    raise ValueError(f"'{op}' does not apply here")


def _range(value):
    parts = [p.strip() for p in str(value).replace(" and ", ",").split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError("Give two values for 'between', e.g. 40, 60")
    return parts


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{value}' is not a number") from None


def _number_clause(expr, op, value):
    if op == "between":
        low, high = (_number(v) for v in _range(value))
        return f"{expr} BETWEEN ? AND ?", [low, high]
    if op in ("=", "<", "<=", ">", ">="):
        return f"{expr} {op} ?", [_number(value)]
    raise ValueError(f"'{op}' does not apply to numbers")


def _date(value):
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError(f"'{value}' is not a date (YYYY-MM-DD)") from None


def _date_clause(expr, op, value):
    if op == "between":
        low, high = (_date(v) for v in _range(value))
        return f"SUBSTR({expr}, 1, 10) BETWEEN ? AND ?", [low, high]
    ops = {"on": "=", "before": "<", "after": ">"}
    if op in ops:
        return f"SUBSTR({expr}, 1, 10) {ops[op]} ?", [_date(value)]
    raise ValueError(f"'{op}' does not apply to dates")


def _module_clause(op, value):
    neg = "NOT " if op == "has not" else ""
    return (f"{neg}EXISTS (SELECT 1 FROM student_modules sm WHERE sm.student_id = s.student_id "
            "AND LOWER(sm.module_code) LIKE LOWER(?) ESCAPE '\\' AND "
            "LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled')", [f"%{_like(value)}%"])


_BUILDERS = {"text": _text_clause, "choice": _choice_clause, "number": _number_clause,
             "date": _date_clause}


def _clause(cond, viewer):
    f = FIELDS.get(cond.get("field"))
    if not f or (f.sensitive and not viewer.can_view_sensitive):
        raise ValueError(f"You cannot search on '{cond.get('field')}'")
    op, value = cond.get("op"), cond.get("value")
    if op not in OPS[f.kind]:
        raise ValueError(f"'{op}' does not apply to {f.label}")
    if op in _NO_VALUE or op == "is empty":
        empty = f"({f.expr} IS NULL OR TRIM({f.expr}) = '')"
        return (empty if op == "is empty" else f"NOT {empty}"), []
    if value in (None, "") and op != "sounds like":
        raise ValueError(f"Enter a value for {f.label}")
    if f.kind == "module":
        return _module_clause(op, value)
    if op == "sounds like":
        return "1 = 1", []      # applied after the query (see _similar)
    return _BUILDERS[f.kind](f.expr, op, value)


def _where(criteria, viewer):
    parts, args = [], []
    for cond in criteria.get("conditions") or []:
        sql, values = _clause(cond, viewer)
        parts.append(sql)
        args += values
    joiner = " OR " if criteria.get("match") == "any" else " AND "
    where = [f"({joiner.join(parts)})"] if parts else []
    text = (criteria.get("text") or "").strip()
    if text:
        quick = [FIELDS[k].expr for k in ("student_id", "name", "email_address", "course")]
        if criteria.get("all_fields"):
            quick = [f.expr for f in fields_for(viewer)
                     if f.kind in ("text", "choice") and f.expr]
        where.append("(" + " OR ".join(f"LOWER(COALESCE({e}, '')) LIKE LOWER(?) ESCAPE '\\'"
                                       for e in quick) + ")")
        args += [f"%{_like(text)}%"] * len(quick)
    where.append("s.student_id NOT LIKE 'ERASED-%'")
    if not viewer.can_view_all:
        where.append("s.student_id = ?")
        args.append(str(viewer.student_id or ""))
    return " AND ".join(where), args


def validate(criteria, viewer: Viewer) -> None:
    """Raise ValueError if the criteria would not run for this viewer."""
    _where(criteria, viewer)


def _select(viewer):
    cols = columns_for(viewer)
    return ", ".join(f"{f.expr} AS {f.key}" for f in cols), [f.key for f in cols]


def _similar(rows, criteria):
    """Apply 'sounds like' conditions (name similarity) in Python."""
    wanted = [(c["field"], str(c.get("value") or "").lower()) for c in
              criteria.get("conditions") or [] if c.get("op") == "sounds like"]
    if not wanted:
        return rows

    def close(row, field, value):
        text = str(row.get(field if field in row else "name") or "").lower()
        candidates = [text] + text.split()
        if max(SequenceMatcher(None, value, t).ratio() for t in candidates) >= SIMILAR_RATIO:
            return True
        # Same sound: every word of the value has a word with its Soundex code.
        wanted = [soundex(w) for w in value.split() if soundex(w)]
        have = {soundex(t) for t in text.split()}
        return bool(wanted) and all(code in have for code in wanted)
    test = any if criteria.get("match") == "any" else all
    return [r for r in rows if test(close(r, f, v) for f, v in wanted)]


def _order(sort, viewer):
    key, _, direction = (sort or "name").partition(" ")
    f = FIELDS.get(key)
    if not f or f not in columns_for(viewer):
        f = FIELDS["name"]
    # Empty values (no mark yet, no attendance) sort last either way.
    return (f"{f.key} IS NULL, {f.key} {'DESC' if direction.lower() == 'desc' else 'ASC'}, "
            "s.student_id")


def _fuzzy(criteria):
    return any(c.get("op") == "sounds like" for c in criteria.get("conditions") or [])


def search(conn, criteria: dict, viewer: Viewer, *, sort="name", page=0, page_size=50,
           audit=True) -> dict:
    """``{"columns", "rows", "total", "page", "page_size"}``; rows are dicts."""
    ensure(conn)
    where, args = _where(criteria, viewer)
    select, columns = _select(viewer)
    order = _order(sort, viewer)
    if _fuzzy(criteria):
        cur = conn.execute(f"SELECT {select} FROM students s WHERE {where} ORDER BY {order} "
                           f"LIMIT {MAX_EXPORT}", args)
        everything = _similar([dict(zip(columns, r)) for r in cur.fetchall()], criteria)
        total, rows = len(everything), everything[page * page_size:(page + 1) * page_size]
    else:
        total = conn.execute(f"SELECT COUNT(*) FROM students s WHERE {where}", args).fetchone()[0]
        cur = conn.execute(f"SELECT {select} FROM students s WHERE {where} ORDER BY {order} "
                           "LIMIT ? OFFSET ?", (*args, int(page_size), int(page) * int(page_size)))
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    if audit:
        record(conn, viewer.username, "search", criteria, total)
    return {"columns": columns, "rows": rows, "total": total, "page": page,
            "page_size": page_size}


def all_ids(conn, criteria, viewer) -> list[str]:
    """Every matching student id (for bulk actions and reports)."""
    ensure(conn)
    where, args = _where(criteria, viewer)
    if _fuzzy(criteria):
        select, columns = _select(viewer)
        rows = conn.execute(f"SELECT {select} FROM students s WHERE {where} LIMIT {MAX_EXPORT}",
                            args).fetchall()
        return [r["student_id"] for r in _similar([dict(zip(columns, x)) for x in rows],
                                                  criteria)]
    return [r[0] for r in conn.execute(f"SELECT s.student_id FROM students s WHERE {where} "
                                       f"ORDER BY s.student_id LIMIT {MAX_EXPORT}", args)]


# ── export and audit ────────────────────────────────────────────────────


def export(conn, criteria, viewer, path, fields=None, fmt="csv", *, ids=None,
           delimiter=",") -> int:
    """Write the matches (only fields the viewer may see) to ``path``; audited.
    ``fmt`` is any of ``table_export.FORMATS`` (CSV, TSV, other delimiter,
    JSON, text, XML, Excel, PDF; SQL for administrators). With ``ids`` only
    those of the matches are written (the selected rows). Returns the number
    of students written."""
    from education_system.systems.university.infrastructure.data_management import (
        table_export,
    )
    if not viewer.can_export:
        raise ValueError("You do not have permission to export student data")
    if fmt not in table_export.FORMATS:
        raise ValueError(f"Unknown export format {fmt!r}")
    if fmt == "sql" and viewer.role not in ADMIN_ROLES:
        raise ValueError("Only an administrator can export SQL statements")
    allowed = [f.key for f in columns_for(viewer)]
    chosen = [k for k in (fields or allowed) if k in allowed] or allowed
    result = search(conn, criteria, viewer, page=0, page_size=MAX_EXPORT, audit=False)
    wanted = {str(i) for i in ids} if ids else None
    rows = [{k: r.get(k) for k in chosen} for r in result["rows"]
            if wanted is None or str(r.get("student_id")) in wanted]
    table_export.write(path, chosen, rows, fmt, title=f"Students: {describe(criteria)}",
                       labels={k: FIELDS[k].label for k in chosen}, delimiter=delimiter)
    record(conn, viewer.username, "export", criteria, len(rows),
           f"{fmt} to {path}; fields: {', '.join(chosen)}"
           + (f"; {len(rows)} selected" if wanted is not None else ""))
    return len(rows)


def suggestions(conn, viewer: Viewer, prefix, limit=10) -> list[str]:
    """Completions for the Find box: student IDs, names and courses that
    start with ``prefix`` (only students the viewer may see)."""
    prefix = str(prefix or "").strip()
    if len(prefix) < 2:
        return []
    ensure(conn)
    scope, args = ("", []) if viewer.can_view_all else (" AND s.student_id = ?",
                                                         [str(viewer.student_id or "")])
    like = f"{_like(prefix)}%"
    found: list[str] = []
    for expr in (FIELDS["student_id"].expr, FIELDS["name"].expr, "s.last_name", _COURSE):
        rows = conn.execute(
            f"SELECT DISTINCT {expr} FROM students s WHERE LOWER(COALESCE({expr}, '')) LIKE "
            f"LOWER(?) ESCAPE '\\' AND s.student_id NOT LIKE 'ERASED-%'{scope} "
            f"ORDER BY 1 LIMIT ?", (like, *args, int(limit))).fetchall()
        found += [str(r[0]) for r in rows if r[0] and str(r[0]) not in found]
    return found[:limit]


def record(conn, actor, action, criteria=None, count=None, detail=None):
    ensure(conn)
    conn.execute("INSERT INTO student_search_audit (actor, action, criteria_json, result_count, "
                 "detail) VALUES (?, ?, ?, ?, ?)",
                 (actor or "unknown", action, json.dumps(criteria) if criteria else None, count,
                  detail))


def describe(criteria) -> str:
    """Criteria in words, for lists, audits and report emails."""
    parts = [f"{FIELDS[c['field']].label if c.get('field') in FIELDS else c.get('field')} "
             f"{c.get('op')} {c.get('value') or ''}".strip()
             for c in (criteria or {}).get("conditions") or []]
    joined = (" OR " if (criteria or {}).get("match") == "any" else " AND ").join(parts)
    text = (criteria or {}).get("text")
    return " AND ".join(p for p in (joined, f"text '{text}'" if text else "") if p) or "everyone"


def audit_tail(conn, limit=200, actor=None) -> list[dict]:
    ensure(conn)
    sql = "SELECT id, actor, action, criteria_json, result_count, detail, at FROM student_search_audit"
    args: tuple = ()
    if actor:
        sql += " WHERE actor = ?"
        args = (actor,)
    rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, int(limit))).fetchall()
    return [{"id": r[0], "actor": r[1], "action": r[2],
             "criteria": describe(json.loads(r[3])) if r[3] else "", "count": r[4],
             "detail": r[5], "at": r[6]} for r in rows]
