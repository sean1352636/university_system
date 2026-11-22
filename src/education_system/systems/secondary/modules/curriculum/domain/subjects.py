"""Subjects: the catalogue of subjects taught in Years 7-11, and the curriculum
plan (lessons per week for each subject in each year).

Teaching groups, the timetable, options, the gradebook and exam entries will
point at a subject by ``subject_id``, so a subject's code and name can change
without breaking them.

Rules:

* Code: 2-8 capital letters or digits, unique (``MATH``, ``ENG``). Name: unique
  ignoring case, up to 64 characters.
* Key stage KS3, KS4 or Both. A KS3-only subject leads to no qualification
  ("KS3"); a GCSE / BTEC / other qualification needs KS4 (or Both). An exam
  board only goes with a qualification.
* EBacc category (English, Maths, Science, Humanities, Languages) feeds the
  EBacc and Attainment 8 later; core means every pupil in those years takes it.
* The curriculum plan holds lessons per week (0-20) for each year the subject
  is taught in; a year outside the subject's key stage can't have lessons.
  Each year's total is checked against the timetable week
  (:func:`periods_per_week`, a school setting) - over is a warning, not an
  error, so a plan can be drafted.
* A subject is retired by making it inactive (it stays on old records). It can
  only be deleted while nothing uses it: any table with a foreign key to
  ``subjects`` counts; :func:`register_usage` just gives it a friendly name.

Every change goes in ``subject_audit`` and the activity log (ids, codes and
field names only).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SUBJECT_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

KEY_STAGES: tuple[str, ...] = ("KS3", "KS4", "Both")
KS_YEARS = {"KS3": (7, 8, 9), "KS4": (10, 11), "Both": (7, 8, 9, 10, 11)}
QUALIFICATIONS: tuple[str, ...] = ("KS3", "GCSE", "BTEC", "Other")
EXAM_BOARDS: tuple[str, ...] = ("AQA", "Pearson Edexcel", "OCR", "WJEC Eduqas", "Other")
EBACC_CATEGORIES: tuple[str, ...] = ("English", "Maths", "Science", "Humanities", "Languages")
MAX_LESSONS = 20
DEFAULT_PERIODS_PER_WEEK = 25

EDITABLE_FIELDS: tuple[str, ...] = (
    "code", "name", "key_stage", "qualification", "exam_board", "spec_code", "department",
    "head_of_subject", "head_of_subject_email", "ebacc_category", "is_core", "notes",
)
FIELD_LABELS = {
    "code": "Code", "name": "Name", "key_stage": "Key stage", "qualification": "Qualification",
    "exam_board": "Exam board", "spec_code": "Specification code", "department": "Department",
    "head_of_subject": "Head of subject", "head_of_subject_email": "Head of subject e-mail",
    "ebacc_category": "EBacc category", "is_core": "Core", "notes": "Notes",
    "is_active": "Active",
}
_CODE_RE = re.compile(r"^[A-Z0-9]{2,8}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code                  TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL UNIQUE COLLATE NOCASE,
    key_stage             TEXT NOT NULL DEFAULT 'Both'
                          CHECK (key_stage IN ('KS3', 'KS4', 'Both')),
    qualification         TEXT NOT NULL DEFAULT 'GCSE'
                          CHECK (qualification IN ('KS3', 'GCSE', 'BTEC', 'Other')),
    exam_board            TEXT,
    spec_code             TEXT,
    department            TEXT,
    head_of_subject       TEXT,
    head_of_subject_email TEXT,
    ebacc_category        TEXT,
    is_core               INTEGER NOT NULL DEFAULT 0,
    is_active             INTEGER NOT NULL DEFAULT 1,
    notes                 TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            TEXT,
    updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by            TEXT
);
CREATE TABLE IF NOT EXISTS subject_curriculum (
    subject_id INTEGER NOT NULL REFERENCES subjects (subject_id) ON DELETE CASCADE,
    year_group INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    lessons    INTEGER NOT NULL CHECK (lessons BETWEEN 1 AND 20),
    PRIMARY KEY (subject_id, year_group)
);
CREATE TABLE IF NOT EXISTS subject_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS subject_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('create', 'update', 'activate', 'deactivate',
                                               'delete', 'curriculum')),
    actor      TEXT NOT NULL,
    detail     TEXT,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_subject_audit ON subject_audit (subject_id, audit_id);
"""

database.register_schema("subjects", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

#: (table, column, what it is) - places that point at a subject. Other areas add
#: theirs with register_usage(); delete refuses while any row uses the subject.
_USAGES: list[tuple[str, str, str]] = []


def register_usage(table: str, column: str, label: str) -> None:
    if not (re.fullmatch(r"[a-z_][a-z0-9_]*", table) and re.fullmatch(r"[a-z_][a-z0-9_]*",
                                                                      column)):
        raise ValueError("bad table/column name")
    if (table, column, label) not in _USAGES:
        _USAGES.append((table, column, label))


@dataclass(frozen=True)
class Subject:
    subject_id: int
    code: str
    name: str
    key_stage: str = "Both"
    qualification: str = "GCSE"
    exam_board: str | None = None
    spec_code: str | None = None
    department: str | None = None
    head_of_subject: str | None = None
    head_of_subject_email: str | None = None
    ebacc_category: str | None = None
    is_core: bool = False
    is_active: bool = True
    notes: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} ({self.code})"

    @property
    def years(self) -> tuple[int, ...]:
        return KS_YEARS[self.key_stage]


# ── Helpers ──────────────────────────────────────────────────────────

def _row(r) -> Subject:
    d = {f.name: r[f.name] for f in fields(Subject)}
    d["is_core"], d["is_active"] = bool(d["is_core"]), bool(d["is_active"])
    return Subject(**d)


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in SUBJECT_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view subjects but not change them.")


def _audit(conn, subject_id: int, action: str, actor: Principal, detail: dict) -> None:
    conn.execute("INSERT INTO subject_audit (subject_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?)",
                 (subject_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True)))


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str]
            ) -> str | None:
    text = P._clean_text(value, 40)
    if not text:
        return None
    match = next((o for o in options if o.lower() == text.lower()), None)
    if match is None:
        problems.append(f"{label} must be one of: {', '.join(options)}")
    return match


def _validate(data: dict[str, Any], current: Subject | None = None) -> dict[str, Any]:
    """Check *data* merged over *current*; return the cleaned changed-or-new fields."""
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    if "code" in data or current is None:
        code = (P._clean_text(data.get("code"), 20) or "").replace(" ", "").upper()
        if not code:
            problems.append("Code is required")
        elif not _CODE_RE.match(code):
            problems.append("Code must be 2-8 capital letters or digits, e.g. MATH")
        out["code"] = code
    if "name" in data or current is None:
        name = P._clean_text(data.get("name"), 200)
        if not name:
            problems.append("Name is required")
        elif len(name) > 64:
            problems.append("Name must be 64 characters or fewer")
        out["name"] = name
    if "key_stage" in data or current is None:
        out["key_stage"] = _choice(data.get("key_stage") or "Both", KEY_STAGES, "Key stage",
                                   problems) or "Both"
    if "qualification" in data or current is None:
        default = "KS3" if out.get("key_stage") == "KS3" else "GCSE"
        out["qualification"] = _choice(data.get("qualification") or default, QUALIFICATIONS,
                                       "Qualification", problems) or default
    if "exam_board" in data:
        out["exam_board"] = _choice(data.get("exam_board"), EXAM_BOARDS, "Exam board", problems)
    if "ebacc_category" in data:
        out["ebacc_category"] = _choice(data.get("ebacc_category"), EBACC_CATEGORIES,
                                        "EBacc category", problems)
    for key, limit in (("spec_code", 20), ("department", 60), ("head_of_subject", 100),
                       ("notes", 2000)):
        if key in data:
            out[key] = P._clean_text(data.get(key), limit)
    if "head_of_subject_email" in data:
        email = P._clean_text(data.get("head_of_subject_email"), 254)
        email = email.lower() if email else None
        if email and not C.valid_email(email):
            problems.append("The head of subject's e-mail address doesn't look right")
        out["head_of_subject_email"] = email
    if "is_core" in data:
        out["is_core"] = bool(P._as_bool(data.get("is_core"), "Core", problems))

    # Rules across fields, on the record as it would be.
    merged = {f: getattr(current, f) if current else None for f in EDITABLE_FIELDS}
    merged.update(out)
    ks, qual = merged["key_stage"], merged["qualification"]
    if ks and qual:
        if ks == "KS3" and qual != "KS3":
            problems.append("A KS3-only subject doesn't lead to a qualification - set "
                            "Qualification to KS3, or Key stage to KS4 or Both")
        if ks == "KS4" and qual == "KS3":
            problems.append("A KS4 subject needs a qualification (GCSE, BTEC or Other)")
        if qual == "KS3" and (merged.get("exam_board") or merged.get("spec_code")):
            problems.append("An exam board and specification only go with a qualification")
    if problems:
        raise ValidationError(problems)
    return out


def _clash(conn, clean: dict[str, Any], not_id: int | None) -> list[str]:
    problems = []
    if "code" in clean and conn.execute(
            "SELECT 1 FROM subjects WHERE code = ? AND subject_id IS NOT ?",
            (clean["code"], not_id)).fetchone():
        problems.append(f"There's already a subject with code {clean['code']}")
    if "name" in clean and conn.execute(
            "SELECT 1 FROM subjects WHERE name = ? COLLATE NOCASE AND subject_id IS NOT ?",
            (clean["name"], not_id)).fetchone():
        problems.append(f"There's already a subject called {clean['name']}")
    return problems


# ── Reading ──────────────────────────────────────────────────────────

def get(subject_id: int) -> Subject:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM subjects WHERE subject_id = ?", (int(subject_id),)
                         ).fetchone()
    if r is None:
        raise NotFound(f"No subject #{subject_id}")
    return _row(r)


def get_by_code(code: str) -> Subject | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM subjects WHERE code = ?",
                         ((code or "").strip().upper(),)).fetchone()
    return _row(r) if r else None


def list_subjects(*, key_stage: str | None = None, qualification: str | None = None,
                  active_only: bool = True, search: str | None = None,
                  year_group: int | None = None) -> list[Subject]:
    """Subjects by name. *key_stage* "KS3"/"KS4" also matches "Both"; *year_group*
    keeps the subjects taught in that year."""
    sql, params = "SELECT * FROM subjects WHERE 1=1", []
    if key_stage in ("KS3", "KS4"):
        sql += " AND key_stage IN (?, 'Both')"
        params.append(key_stage)
    elif key_stage == "Both":
        sql += " AND key_stage = 'Both'"
    if qualification:
        sql += " AND qualification = ?"
        params.append(qualification)
    if active_only:
        sql += " AND is_active = 1"
    if search:
        sql += " AND (code LIKE ? OR name LIKE ? OR department LIKE ?)"
        params += [f"%{search.strip()}%"] * 3
    sql += " ORDER BY name COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, params)]
    if year_group is not None:
        rows = [s for s in rows if int(year_group) in s.years]
    return rows


def departments() -> list[str]:
    with database.connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT department FROM subjects WHERE department IS NOT NULL "
            "ORDER BY department COLLATE NOCASE")]


def counts() -> dict[str, int]:
    with database.connect() as conn:
        r = conn.execute("SELECT COUNT(*) total, coalesce(SUM(is_active), 0) active, "
                         "coalesce(SUM(is_core AND is_active), 0) core FROM subjects").fetchone()
    return {"total": r["total"], "active": r["active"], "inactive": r["total"] - r["active"],
            "core": r["core"]}


def history(subject_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM subject_audit WHERE subject_id = ? "
                            "ORDER BY audit_id DESC", (int(subject_id),)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


def usage(subject_id: int) -> list[tuple[str, int]]:
    """[(what, rows)] for every place using the subject: each table with a foreign key
    to ``subjects`` (found from the schema, so nothing can be missed) plus any
    registered with :func:`register_usage`. Labels come from the registrations."""
    labels = {(t, c): label for t, c, label in _USAGES}
    out = []
    with database.connect() as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        refs = set(labels)
        for t in tables:
            if t == "subject_curriculum":  # the subject's own plan; deleted with it
                continue
            for fk in conn.execute(f"PRAGMA foreign_key_list('{t}')"):  # nosec B608 - names from sqlite_master
                if fk["table"] == "subjects":
                    refs.add((t, fk["from"]))
        for table, column in sorted(refs):
            if table not in tables:
                continue
            n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?',  # nosec B608 - names from schema / register_usage
                             (int(subject_id),)).fetchone()[0]
            if n:
                out.append((labels.get((table, column), table.replace("_", " ")), n))
    return out


# ── Changing subjects ────────────────────────────────────────────────

def create(data: dict[str, Any], *, actor: Principal) -> Subject:
    _require(actor, "subject.create")
    clean = _validate(data)
    with database.connect() as conn:
        clash = _clash(conn, clean, None)
        if clash:
            raise ValidationError(clash)
        cols = list(clean)
        cur = conn.execute(
            f"INSERT INTO subjects ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - cols from EDITABLE_FIELDS
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username))
        sid = cur.lastrowid
        _audit(conn, sid, "create", actor, {"code": clean["code"]})
    activity_log.record("subject.create", target=clean["code"], principal=actor)
    return get(sid)


def update(subject_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> tuple[Subject, list[str]]:
    """Change a subject. Returns (subject, changed field names). Narrowing the key
    stage drops planned lessons in years it no longer covers."""
    _require(actor, "subject.update", f"S{subject_id}")
    current = get(subject_id)
    try:
        clean = _validate(changes, current)
    except ValidationError as e:
        activity_log.record("subject.update", target=current.code, outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    diff = {k: {"from": getattr(current, k), "to": v} for k, v in clean.items()
            if getattr(current, k) != v}
    if not diff:
        return current, []
    with database.connect() as conn:
        clash = _clash(conn, {k: clean[k] for k in diff if k in ("code", "name")}, subject_id)
        if clash:
            raise ValidationError(clash)
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE subjects SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from EDITABLE_FIELDS
                     "updated_by = ? WHERE subject_id = ?",
                     (*(d["to"] for d in diff.values()), actor.username, subject_id))
        dropped = 0
        if "key_stage" in diff:
            keep = KS_YEARS[diff["key_stage"]["to"]]
            dropped = conn.execute(
                f"DELETE FROM subject_curriculum WHERE subject_id = ? AND year_group NOT IN "  # nosec B608 - ints
                f"({', '.join(str(y) for y in keep)})", (subject_id,)).rowcount
        detail = {k: ("changed" if k in {"head_of_subject_email", "notes"} else d)
                  for k, d in diff.items()}
        if dropped:
            detail["lessons_dropped_years"] = dropped
        _audit(conn, subject_id, "update", actor, detail)
    activity_log.record("subject.update", target=current.code, principal=actor,
                        fields=sorted(diff))
    return get(subject_id), sorted(diff)


def set_active(subject_id: int, active: bool, *, actor: Principal) -> Subject:
    _require(actor, "subject.activate" if active else "subject.deactivate", f"S{subject_id}")
    s = get(subject_id)
    if s.is_active == bool(active):
        return s
    with database.connect() as conn:
        conn.execute("UPDATE subjects SET is_active = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE subject_id = ?",
                     (int(bool(active)), actor.username, subject_id))
        _audit(conn, subject_id, "activate" if active else "deactivate", actor, {})
    activity_log.record("subject.activate" if active else "subject.deactivate",
                        target=s.code, principal=actor)
    return get(subject_id)


def toggle_active(subject_id: int, *, actor: Principal) -> Subject:
    return set_active(subject_id, not get(subject_id).is_active, actor=actor)


def delete(subject_id: int, *, actor: Principal) -> None:
    """Delete a subject added by mistake. Refused while anything uses it -
    make it inactive instead. Its history is kept."""
    _require(actor, "subject.delete", f"S{subject_id}")
    s = get(subject_id)
    used = usage(subject_id)
    if used:
        raise ValidationError([f"{s.code} is used by " + ", ".join(
            f"{n} {what}" for what, n in used) + " - make it inactive instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
        _audit(conn, subject_id, "delete", actor, {"code": s.code, "name": s.name})
    activity_log.record("subject.delete", target=s.code, principal=actor)


# ── Curriculum plan ──────────────────────────────────────────────────

def periods_per_week() -> int:
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM subject_settings WHERE key = 'periods_per_week'"
                         ).fetchone()
    try:
        return int(r["value"]) if r else DEFAULT_PERIODS_PER_WEEK
    except (TypeError, ValueError):
        return DEFAULT_PERIODS_PER_WEEK


def set_periods_per_week(value: Any, *, actor: Principal) -> int:
    _require(actor, "subject.settings")
    try:
        n = int(str(value).strip())
    except ValueError:
        n = 0
    if not 10 <= n <= 60:
        raise ValidationError(["Lessons in the timetable week must be from 10 to 60"])
    with database.connect() as conn:
        conn.execute("INSERT INTO subject_settings (key, value) VALUES ('periods_per_week', ?) "
                     "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(n),))
    activity_log.record("subject.settings", principal=actor, periods_per_week=n)
    return n


def lessons(subject_id: int) -> dict[int, int]:
    """{year: lessons per week} for one subject (years with none left out)."""
    with database.connect() as conn:
        return {r["year_group"]: r["lessons"] for r in conn.execute(
            "SELECT year_group, lessons FROM subject_curriculum WHERE subject_id = ?",
            (int(subject_id),))}


def plan(*, active_only: bool = True) -> dict[int, dict[int, int]]:
    """{subject_id: {year: lessons}} for the whole curriculum."""
    out: dict[int, dict[int, int]] = {}
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT c.subject_id, c.year_group, c.lessons FROM subject_curriculum c "
            "JOIN subjects s USING (subject_id)"
            + (" WHERE s.is_active = 1" if active_only else "")).fetchall()
    for r in rows:
        out.setdefault(r["subject_id"], {})[r["year_group"]] = r["lessons"]
    return out


def year_totals() -> dict[int, int]:
    totals = {y: 0 for y in P.YEAR_GROUPS}
    for by_year in plan().values():
        for y, n in by_year.items():
            totals[y] += n
    return totals


def set_lessons(subject_id: int, by_year: dict[Any, Any], *, actor: Principal
                ) -> tuple[dict[int, int], list[str]]:
    """Set lessons per week for some years (0 or blank removes). Returns (the subject's
    plan now, warnings about years over the timetable week)."""
    _require(actor, "subject.curriculum", f"S{subject_id}")
    s = get(subject_id)
    problems, clean = [], {}
    for raw_year, raw in by_year.items():
        try:
            y = int(raw_year)
        except (TypeError, ValueError):
            problems.append(f"Unknown year {raw_year}")
            continue
        if y not in P.YEAR_GROUPS:
            problems.append(f"Unknown year {raw_year}")
            continue
        text = "" if raw is None else str(raw).strip()
        try:
            n = int(text) if text else 0
        except ValueError:
            problems.append(f"Year {y}: lessons must be a whole number")
            continue
        if not 0 <= n <= MAX_LESSONS:
            problems.append(f"Year {y}: lessons must be from 0 to {MAX_LESSONS}")
        elif n and y not in s.years:
            problems.append(f"Year {y} isn't in {s.code}'s key stage ({s.key_stage})")
        clean[y] = n
    if problems:
        raise ValidationError(problems)
    before = lessons(subject_id)
    changed = {y: {"from": before.get(y, 0), "to": n} for y, n in clean.items()
               if before.get(y, 0) != n}
    if changed:
        with database.connect() as conn:
            for y, d in changed.items():
                if d["to"]:
                    conn.execute("INSERT INTO subject_curriculum (subject_id, year_group, lessons) "
                                 "VALUES (?, ?, ?) ON CONFLICT (subject_id, year_group) DO UPDATE "
                                 "SET lessons = excluded.lessons", (subject_id, y, d["to"]))
                else:
                    conn.execute("DELETE FROM subject_curriculum WHERE subject_id = ? AND "
                                 "year_group = ?", (subject_id, y))
            _audit(conn, subject_id, "curriculum", actor, {str(y): d for y, d in changed.items()})
        activity_log.record("subject.curriculum", target=s.code, principal=actor,
                            years=sorted(changed))
    return lessons(subject_id), plan_warnings(years=list(clean))


def plan_warnings(years: list[int] | None = None) -> list[str]:
    """Years whose planned lessons go over the timetable week, and core subjects
    with no lessons planned in a year they cover."""
    week, totals, out = periods_per_week(), year_totals(), []
    for y in years or P.YEAR_GROUPS:
        if totals.get(y, 0) > week:
            out.append(f"Year {y} has {totals[y]} lessons planned - the timetable week has "
                       f"{week}")
    if years is None:
        p = plan()
        for s in list_subjects():
            if s.is_core:
                missing = [y for y in s.years if not p.get(s.subject_id, {}).get(y)]
                if missing:
                    out.append(f"Core subject {s.code} has no lessons planned in Year "
                               + ", ".join(map(str, missing)))
    return out


# ── Standard subjects ────────────────────────────────────────────────

#: A starting catalogue for an English secondary school. Only added on request,
#: and only codes not already there.
STANDARD_SUBJECTS: tuple[dict[str, Any], ...] = (
    {"code": "ENG", "name": "English Language", "ebacc_category": "English", "is_core": True,
     "department": "English"},
    {"code": "ENGLIT", "name": "English Literature", "key_stage": "KS4",
     "ebacc_category": "English", "is_core": True, "department": "English"},
    {"code": "MATH", "name": "Mathematics", "ebacc_category": "Maths", "is_core": True,
     "department": "Mathematics"},
    {"code": "SCI", "name": "Science", "key_stage": "KS3", "qualification": "KS3",
     "is_core": True, "department": "Science"},
    {"code": "COMBSCI", "name": "Combined Science", "key_stage": "KS4",
     "ebacc_category": "Science", "department": "Science"},
    {"code": "BIO", "name": "Biology", "key_stage": "KS4", "ebacc_category": "Science",
     "department": "Science"},
    {"code": "CHEM", "name": "Chemistry", "key_stage": "KS4", "ebacc_category": "Science",
     "department": "Science"},
    {"code": "PHYS", "name": "Physics", "key_stage": "KS4", "ebacc_category": "Science",
     "department": "Science"},
    {"code": "HIST", "name": "History", "ebacc_category": "Humanities",
     "department": "Humanities"},
    {"code": "GEOG", "name": "Geography", "ebacc_category": "Humanities",
     "department": "Humanities"},
    {"code": "FREN", "name": "French", "ebacc_category": "Languages", "department": "Languages"},
    {"code": "SPAN", "name": "Spanish", "ebacc_category": "Languages",
     "department": "Languages"},
    {"code": "COMP", "name": "Computer Science", "ebacc_category": "Science",
     "department": "Computing"},
    {"code": "RE", "name": "Religious Studies", "department": "Humanities"},
    {"code": "ART", "name": "Art and Design", "department": "Creative Arts"},
    {"code": "DT", "name": "Design and Technology", "department": "Technology"},
    {"code": "FOOD", "name": "Food Preparation and Nutrition", "department": "Technology"},
    {"code": "MUS", "name": "Music", "department": "Creative Arts"},
    {"code": "DRAMA", "name": "Drama", "department": "Creative Arts"},
    {"code": "PE", "name": "Physical Education", "qualification": "Other", "is_core": True,
     "department": "PE", "notes": "Core PE (non-examined). Add GCSE PE separately."},
    {"code": "PSHE", "name": "PSHE and RSE", "qualification": "Other", "is_core": True,
     "department": "Personal Development", "notes": "Statutory RSE; non-examined."},
)


def missing_standard() -> list[dict[str, Any]]:
    with database.connect() as conn:
        codes = {r[0] for r in conn.execute("SELECT code FROM subjects")}
        names = {r[0].lower() for r in conn.execute("SELECT name FROM subjects")}
    return [d for d in STANDARD_SUBJECTS
            if d["code"] not in codes and d["name"].lower() not in names]


def add_standard(codes: list[str] | None = None, *, actor: Principal) -> list[Subject]:
    """Add the standard subjects that aren't there yet (or just *codes*)."""
    _require(actor, "subject.create")
    made = []
    for d in missing_standard():
        if codes is None or d["code"] in codes:
            made.append(create(d, actor=actor))
    return made
