"""Entry requirements, applicant GCSE results and structured offer conditions.

Three linked pieces of the admissions pipeline, all in the admissions
(students) database:

* ``admissions_entry_requirements`` / ``admissions_requirement_subjects``
  — what a programme asks for. Keyed by *programme name*: a subject or
  course name exactly as the applicant chooses it (``"Mathematics"``,
  ``"BTEC Applied Science"``) or :data:`GENERAL_PROGRAMME` for the
  college-wide minimum. A requirement can ask for

    - a minimum number of GCSEs at or above a grade (``5 at grade 4``),
    - a minimum average GCSE point score,
    - specific GCSE subject minimums (``Mathematics 7``, ``English 4``).

  Subjects and courses themselves belong to the academics modules; this
  table only stores admissions rules against their names.

* ``admissions_applicant_gcses`` — the applicant's GCSEs, either
  *Predicted* (from the application or the feeder reference) or *Actual*
  (entered or imported on results day). Grades use the 9-1 scale or a
  legacy A*-G letter, scored with prior_attainment's DfE points.

* ``admissions_offer_conditions`` — a conditional offer as structured
  rows, generated from the requirements of every programme the applicant
  chose (still editable, and free-text "other" conditions can be added).
  The applicant's ``offer_conditions`` text is rebuilt from these rows so
  letters and older screens keep working. :func:`evaluate` marks each row
  Met / Not met / Near miss against the GCSE results.

"Near miss" means one grade short: a subject one grade under its
minimum, one GCSE short of a count (or the count met one grade lower),
or an average that one more grade in one subject would have reached.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

#: Programme name for the college-wide minimum entry requirement.
GENERAL_PROGRAMME: str = "Sixth form (general)"

RESULT_TYPES: tuple[str, ...] = ("Predicted", "Actual")
RESULT_SOURCES: tuple[str, ...] = (
    "Entered", "Application", "Reference", "Imported CSV", "CTF", "Online",
    "Transfer",
)
GCSE_KINDS: tuple[str, ...] = ("GCSE", "GCSE short course", "IGCSE")
GCSE_91_GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5", "4", "3", "2",
                                   "1", "U")
LEGACY_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "F", "G",
                                  "U")

CONDITION_KINDS: tuple[str, ...] = (
    "gcse_count", "subject_grade", "average_points", "other",
)
OUTCOMES: tuple[str, ...] = ("Pending", "Met", "Near miss", "Not met",
                             "Manual")
#: Outcomes a member of staff may set by hand on any condition.
MANUAL_OUTCOMES: tuple[str, ...] = ("Met", "Near miss", "Not met")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_entry_requirements (
    req_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    programme           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    min_gcse_count      INTEGER,
    min_gcse_grade      INTEGER,
    min_average_points  REAL,
    notes               TEXT,
    updated_by          TEXT,
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admissions_requirement_subjects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id        INTEGER NOT NULL,
    gcse_subject  TEXT NOT NULL,
    min_grade     INTEGER NOT NULL,
    UNIQUE (req_id, gcse_subject),
    FOREIGN KEY (req_id) REFERENCES admissions_entry_requirements(req_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admissions_applicant_gcses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    subject       TEXT NOT NULL,
    grade         TEXT NOT NULL,
    grade_system  TEXT NOT NULL DEFAULT '9-1',
    kind          TEXT NOT NULL DEFAULT 'GCSE',
    result_type   TEXT NOT NULL DEFAULT 'Predicted',
    year          INTEGER,
    exam_board    TEXT,
    source        TEXT NOT NULL DEFAULT 'Entered',
    entered_by    TEXT,
    entered_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (applicant_id, subject, kind, result_type),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_gcse_aid
    ON admissions_applicant_gcses(applicant_id);

CREATE TABLE IF NOT EXISTS admissions_offer_conditions (
    condition_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id    TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'other',
    subject         TEXT,
    min_grade       INTEGER,
    min_count       INTEGER,
    min_points      REAL,
    description     TEXT NOT NULL,
    source_programme TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    outcome         TEXT NOT NULL DEFAULT 'Pending',
    outcome_detail  TEXT,
    manual_outcome  TEXT,
    evaluated_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_cond_aid
    ON admissions_offer_conditions(applicant_id);
"""


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class Requirement:
    req_id: int
    programme: str
    min_gcse_count: int | None
    min_gcse_grade: int | None
    min_average_points: float | None
    notes: str | None
    updated_by: str | None
    updated_at: str | None
    subject_minimums: dict[str, int] = field(default_factory=dict)

    def describe(self) -> list[str]:
        out = []
        if self.min_gcse_count:
            out.append(f"{self.min_gcse_count} GCSEs at grade "
                       f"{self.min_gcse_grade or 4} or above")
        for subj, g in self.subject_minimums.items():
            out.append(f"GCSE {subj} grade {g} or above")
        if self.min_average_points:
            out.append(f"Average GCSE point score of at least "
                       f"{self.min_average_points:g}")
        return out


@dataclass
class GCSE:
    id: int
    applicant_id: str
    subject: str
    grade: str
    grade_system: str
    kind: str
    result_type: str
    year: int | None
    exam_board: str | None
    source: str
    entered_by: str | None
    entered_at: str | None

    @property
    def points(self) -> float | None:
        return grade_points(self.grade, self.grade_system)


@dataclass
class OfferCondition:
    condition_id: int
    applicant_id: str
    kind: str
    subject: str | None
    min_grade: int | None
    min_count: int | None
    min_points: float | None
    description: str
    source_programme: str | None
    sort_order: int
    outcome: str
    outcome_detail: str | None
    manual_outcome: str | None
    evaluated_at: str | None

    @property
    def effective_outcome(self) -> str:
        return self.manual_outcome or self.outcome


@dataclass
class Evaluation:
    applicant_id: str
    result_type: str               # which results were used
    overall: str                   # Met / Near miss / Not met / Pending
    conditions: list[OfferCondition]
    results_used: int

    @property
    def met(self) -> bool:
        return self.overall == "Met"


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    return _adm._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _username() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def _log(applicant_id: str, detail: str, kind: str = "offer") -> None:
    with _connect() as conn:
        _adm._log_event(conn, applicant_id, detail, kind=kind)
        conn.commit()


# ── Grade helpers ──────────────────────────────────────────────────

_LEGACY_POINTS = {"A*": 8.5, "A": 7.0, "B": 5.5, "C": 4.0, "D": 3.0,
                  "E": 2.0, "F": 1.5, "G": 1.0, "U": 0.0}


def grade_points(grade: str | None, grade_system: str | None = None
                 ) -> float | None:
    """9-1 point value (legacy letters on DfE transition points).

    Uses the qualifications module's scoring so admissions and prior
    attainment agree; falls back to the same table if it is unavailable.
    """
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            prior_attainment as _prior,
        )
        return _prior.grade_points(grade, grade_system)
    except ImportError:
        if not grade:
            return None
        g = grade.strip().upper()
        if g in GCSE_91_GRADES:
            return 0.0 if g == "U" else float(g)
        return _LEGACY_POINTS.get(g)


def _area(subject: str | None) -> str | None:
    """'English' / 'Maths' when the subject counts for that area."""
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            prior_attainment as _prior,
        )
        return _prior.area_for_subject(subject)
    except ImportError:
        s = (subject or "").strip().lower()
        if s in ("maths", "math", "mathematics"):
            return "Maths"
        if s.startswith("english"):
            return "English"
        return None


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def subject_matches(required: str, result_subject: str) -> bool:
    """Whether a GCSE result counts for a required GCSE subject.

    Exact (case-insensitive) match; English / Maths by area (English
    Language or Literature both count for "English"); otherwise the
    required name as a whole word of the result ("Science" matches
    "Combined Science", "Biology" matches "Biology (triple)").
    """
    r, s = _norm(required), _norm(result_subject)
    if not r or not s:
        return False
    if r == s:
        return True
    ra = _area(required)
    if ra and ra == _area(result_subject):
        return True
    return re.search(rf"\b{re.escape(r)}\b", s) is not None


def _validate_grade(grade: Any, grade_system: Any = None) -> tuple[str, str]:
    g = str(grade or "").strip().upper()
    if not g:
        raise ValidationError("Grade is required")
    system = str(grade_system or "").strip() or (
        "9-1" if g in GCSE_91_GRADES else "A*-G")
    if system not in ("9-1", "A*-G"):
        raise ValidationError("Grade system must be 9-1 or A*-G")
    allowed = GCSE_91_GRADES if system == "9-1" else LEGACY_GRADES
    if g not in allowed:
        raise ValidationError(
            f"A {system} GCSE grade must be one of: {', '.join(allowed)}")
    return g, system


def _int_grade(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a 9-1 grade (1-9)") from None
    if not 1 <= n <= 9:
        raise ValidationError(f"{label} must be between 1 and 9")
    return n


# ── Entry requirements ─────────────────────────────────────────────

def _row_req(conn: db.Connection, r: db.Row) -> Requirement:
    subs = {x["gcse_subject"]: x["min_grade"] for x in conn.execute(
        "SELECT gcse_subject, min_grade FROM admissions_requirement_subjects "
        "WHERE req_id = ? ORDER BY id", (r["req_id"],)).fetchall()}
    return Requirement(
        req_id=r["req_id"], programme=r["programme"],
        min_gcse_count=r["min_gcse_count"],
        min_gcse_grade=r["min_gcse_grade"],
        min_average_points=r["min_average_points"],
        notes=r["notes"], updated_by=r["updated_by"],
        updated_at=r["updated_at"], subject_minimums=subs)


def set_requirement(programme: str, *,
                    min_gcse_count: Any = None,
                    min_gcse_grade: Any = None,
                    min_average_points: Any = None,
                    subject_minimums: dict[str, Any] | None = None,
                    notes: str | None = None,
                    updated_by: str | None = None) -> Requirement:
    """Create or replace the entry requirement for a programme."""
    init_db()
    name = (programme or "").strip()
    if not name:
        raise ValidationError("Programme (subject or course name) is required")
    if len(name) > 120:
        raise ValidationError("Programme name is too long")
    count = None
    if min_gcse_count not in (None, ""):
        try:
            count = int(min_gcse_count)
        except (TypeError, ValueError):
            raise ValidationError("Number of GCSEs must be a whole number") from None
        if not 1 <= count <= 15:
            raise ValidationError("Number of GCSEs must be between 1 and 15")
    grade = _int_grade(min_gcse_grade, "Minimum GCSE grade")
    if count and grade is None:
        grade = 4
    avg = None
    if min_average_points not in (None, ""):
        try:
            avg = round(float(min_average_points), 2)
        except (TypeError, ValueError):
            raise ValidationError("Average point score must be a number") from None
        if not 0 < avg <= 9:
            raise ValidationError("Average point score must be between 0 and 9")
    subs: dict[str, int] = {}
    for subj, g in (subject_minimums or {}).items():
        s = (subj or "").strip()
        if not s:
            continue
        gi = _int_grade(g, f"Minimum grade for {s}")
        if gi is None:
            raise ValidationError(f"Minimum grade for {s} is required")
        subs[s] = gi
    if not (count or avg or subs):
        raise ValidationError(
            "Give at least one rule: a number of GCSEs, an average point "
            "score or a subject minimum")
    by = updated_by or _username()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_entry_requirements
                   (programme, min_gcse_count, min_gcse_grade,
                    min_average_points, notes, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(programme) DO UPDATE SET
                   min_gcse_count = excluded.min_gcse_count,
                   min_gcse_grade = excluded.min_gcse_grade,
                   min_average_points = excluded.min_average_points,
                   notes = excluded.notes,
                   updated_by = excluded.updated_by,
                   updated_at = excluded.updated_at""",
            (name, count, grade, avg, (notes or "").strip() or None, by))
        rid = conn.execute(
            "SELECT req_id FROM admissions_entry_requirements "
            "WHERE programme = ?", (name,)).fetchone()["req_id"]
        conn.execute("DELETE FROM admissions_requirement_subjects "
                     "WHERE req_id = ?", (rid,))
        for s, g in subs.items():
            conn.execute(
                "INSERT INTO admissions_requirement_subjects "
                "(req_id, gcse_subject, min_grade) VALUES (?, ?, ?)",
                (rid, s, g))
        conn.commit()
    logger.info("Entry requirement for %s saved by %s", name, by or "?")
    out = get_requirement(name)
    assert out is not None
    return out


def get_requirement(programme: str) -> Requirement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_entry_requirements WHERE programme = ?",
            ((programme or "").strip(),)).fetchone()
        return _row_req(conn, r) if r else None


def list_requirements() -> list[Requirement]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_entry_requirements "
            "ORDER BY CASE WHEN programme = ? THEN 0 ELSE 1 END, programme",
            (GENERAL_PROGRAMME,)).fetchall()
        return [_row_req(conn, r) for r in rows]


def delete_requirement(programme: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM admissions_entry_requirements WHERE programme = ?",
            ((programme or "").strip(),))
        conn.commit()
    return cur.rowcount > 0


def programmes_without_requirements() -> list[str]:
    """Programme names applicants have chosen that have no requirement."""
    have = {_norm(r.programme) for r in list_requirements()}
    seen: dict[str, str] = {}
    for a in _adm.list_applicants(open_only=True):
        for c in _adm.list_programme_choices(a.applicant_id):
            if _norm(c.subject) not in have:
                seen.setdefault(_norm(c.subject), c.subject)
    return sorted(seen.values())


def requirements_for_applicant(applicant_id: str) -> list[Requirement]:
    """The general requirement plus one per programme chosen."""
    out: list[Requirement] = []
    general = get_requirement(GENERAL_PROGRAMME)
    if general:
        out.append(general)
    for c in _adm.list_programme_choices(applicant_id):
        r = get_requirement(c.subject) or get_requirement(c.label)
        if r and all(r.req_id != x.req_id for x in out):
            out.append(r)
    return out


# ── Applicant GCSE results ─────────────────────────────────────────

def _row_gcse(r: db.Row) -> GCSE:
    return GCSE(id=r["id"], applicant_id=r["applicant_id"],
                subject=r["subject"], grade=r["grade"],
                grade_system=r["grade_system"], kind=r["kind"],
                result_type=r["result_type"], year=r["year"],
                exam_board=r["exam_board"], source=r["source"],
                entered_by=r["entered_by"], entered_at=r["entered_at"])


def record_gcse(applicant_id: str, subject: str, grade: str, *,
                result_type: str = "Actual", kind: str = "GCSE",
                grade_system: str | None = None, year: Any = None,
                exam_board: str | None = None, source: str = "Entered",
                entered_by: str | None = None) -> GCSE:
    """Record (or replace) one GCSE for an applicant."""
    init_db()
    if _adm.get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    subj = (subject or "").strip()
    if not subj:
        raise ValidationError("Subject is required")
    if len(subj) > 80:
        raise ValidationError("Subject name is too long")
    g, system = _validate_grade(grade, grade_system)
    if result_type not in RESULT_TYPES:
        raise ValidationError(f"Result type must be one of: "
                              f"{', '.join(RESULT_TYPES)}")
    if kind not in GCSE_KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(GCSE_KINDS)}")
    if source not in RESULT_SOURCES:
        source = "Entered"
    y = None
    if year not in (None, ""):
        try:
            y = int(year)
        except (TypeError, ValueError):
            raise ValidationError("Year must be a four-digit year") from None
        if not 1980 <= y <= 2100:
            raise ValidationError("Year must be between 1980 and 2100")
    by = entered_by or _username()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_applicant_gcses
                   (applicant_id, subject, grade, grade_system, kind,
                    result_type, year, exam_board, source, entered_by,
                    entered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(applicant_id, subject, kind, result_type)
               DO UPDATE SET grade = excluded.grade,
                   grade_system = excluded.grade_system,
                   year = excluded.year, exam_board = excluded.exam_board,
                   source = excluded.source,
                   entered_by = excluded.entered_by,
                   entered_at = excluded.entered_at""",
            (applicant_id, subj, g, system, kind, result_type, y,
             (exam_board or "").strip() or None, source, by))
        r = conn.execute(
            "SELECT * FROM admissions_applicant_gcses WHERE applicant_id = ? "
            "AND subject = ? AND kind = ? AND result_type = ?",
            (applicant_id, subj, kind, result_type)).fetchone()
        conn.commit()
    return _row_gcse(r)


def list_gcses(applicant_id: str, *, result_type: str | None = None
               ) -> list[GCSE]:
    init_db()
    sql = "SELECT * FROM admissions_applicant_gcses WHERE applicant_id = ?"
    args: list[Any] = [applicant_id]
    if result_type:
        sql += " AND result_type = ?"
        args.append(result_type)
    sql += " ORDER BY result_type, subject"
    with _connect() as conn:
        return [_row_gcse(r) for r in conn.execute(sql, args).fetchall()]


def delete_gcse(gcse_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM admissions_applicant_gcses "
                           "WHERE id = ?", (int(gcse_id),))
        conn.commit()
    return cur.rowcount > 0


_GCSE_TEXT_RE = re.compile(
    r"([A-Za-z][A-Za-z &/().'-]*?)(?:\s+|\s*[:=\-]\s*)(A\*|[1-9]|[A-GU])(?![A-Za-z0-9*])")


def parse_gcse_text(text: str | None) -> list[tuple[str, str]]:
    """``[(subject, grade)]`` from free text like "Maths 7, English 6".

    Entries are split on commas, semicolons and new lines; anything that
    does not end in a recognisable grade is skipped (and listed by the
    caller as unparsed), so nothing is guessed.
    """
    out: list[tuple[str, str]] = []
    for part in re.split(r"[,;\n]+", text or ""):
        m = _GCSE_TEXT_RE.fullmatch(part.strip())
        if m:
            subj = m.group(1).strip(" -:")
            if subj:
                out.append((subj, m.group(2).upper()))
    return out


def import_predicted_from_text(applicant_id: str, *,
                               source: str = "Application",
                               entered_by: str | None = None
                               ) -> tuple[int, list[str]]:
    """Turn the applicant's free-text predicted GCSEs into rows.

    Returns (rows recorded, parts that could not be read).
    """
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    parsed = parse_gcse_text(a.predicted_gcses)
    parts = [p.strip() for p in re.split(r"[,;\n]+", a.predicted_gcses or "")
             if p.strip()]
    readable = {f"{s} {g}".lower() for s, g in parsed}
    unparsed = [p for p in parts
                if re.sub(r"[\s:=\-]+", " ", p).strip().lower() not in readable]
    n = 0
    for subj, grade in parsed:
        try:
            record_gcse(applicant_id, subj, grade, result_type="Predicted",
                        source=source, entered_by=entered_by)
            n += 1
        except ValidationError as e:
            unparsed.append(f"{subj} {grade} ({e})")
    if n:
        _log(applicant_id, f"{n} predicted GCSE(s) read from the "
                           "application text", kind="update")
    return n, unparsed


def import_results_csv(path: str, *, result_type: str = "Actual",
                       entered_by: str | None = None
                       ) -> tuple[int, list[str]]:
    """Import GCSE results from a CSV.

    Columns: ``applicant_id`` (or ``uln`` / ``upn``), ``subject``,
    ``grade``; optional ``kind``, ``year``, ``exam_board``. Returns
    (rows recorded, per-row errors).
    """
    init_db()
    by_uln: dict[str, str] = {}
    by_upn: dict[str, str] = {}
    for a in _adm.list_applicants():
        if a.uln:
            by_uln[a.uln] = a.applicant_id
        if a.upn:
            by_upn[a.upn.upper()] = a.applicant_id
    created, errors = 0, []
    touched: set[str] = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            row = {(k or "").strip().lower(): (v or "").strip()
                   for k, v in row.items()}
            aid = (row.get("applicant_id")
                   or by_uln.get(row.get("uln", ""))
                   or by_upn.get(row.get("upn", "").upper()))
            if not aid:
                errors.append(f"Row {i}: no matching applicant")
                continue
            try:
                record_gcse(aid, row.get("subject", ""), row.get("grade", ""),
                            result_type=result_type,
                            kind=row.get("kind") or "GCSE",
                            year=row.get("year") or None,
                            exam_board=row.get("exam_board") or None,
                            source="Imported CSV", entered_by=entered_by)
                created += 1
                touched.add(aid)
            except ValidationError as e:
                errors.append(f"Row {i}: {e}")
    for aid in touched:
        _log(aid, f"{result_type} GCSE results imported from CSV",
             kind="update")
    logger.info("Imported %d GCSE result rows from %s (%d errors)",
                created, path, len(errors))
    return created, errors


# ── Structured offer conditions ────────────────────────────────────

def _row_cond(r: db.Row) -> OfferCondition:
    return OfferCondition(
        condition_id=r["condition_id"], applicant_id=r["applicant_id"],
        kind=r["kind"], subject=r["subject"], min_grade=r["min_grade"],
        min_count=r["min_count"], min_points=r["min_points"],
        description=r["description"],
        source_programme=r["source_programme"], sort_order=r["sort_order"],
        outcome=r["outcome"], outcome_detail=r["outcome_detail"],
        manual_outcome=r["manual_outcome"], evaluated_at=r["evaluated_at"])


def list_conditions(applicant_id: str) -> list[OfferCondition]:
    init_db()
    with _connect() as conn:
        return [_row_cond(r) for r in conn.execute(
            "SELECT * FROM admissions_offer_conditions WHERE applicant_id = ?"
            " ORDER BY sort_order, condition_id", (applicant_id,)).fetchall()]


def get_condition(condition_id: int) -> OfferCondition | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM admissions_offer_conditions "
                         "WHERE condition_id = ?", (int(condition_id),)
                         ).fetchone()
    return _row_cond(r) if r else None


def _describe(kind: str, subject: str | None, min_grade: int | None,
              min_count: int | None, min_points: float | None) -> str:
    if kind == "gcse_count":
        return f"{min_count} GCSEs at grade {min_grade} or above"
    if kind == "subject_grade":
        return f"GCSE {subject} grade {min_grade} or above"
    if kind == "average_points":
        return f"Average GCSE point score of at least {min_points:g}"
    return ""


def _proposed(applicant_id: str) -> list[dict[str, Any]]:
    """Merge every applicable requirement into a de-duplicated list."""
    return _merge(requirements_for_applicant(applicant_id))


def _merge(requirements: list[Requirement]) -> list[dict[str, Any]]:
    """Requirements merged into de-duplicated condition proposals (the
    strictest of each kind wins)."""
    counts: dict[int, tuple[int, str]] = {}      # grade -> (count, programme)
    subjects: dict[str, tuple[int, str, str]] = {}  # norm -> (grade, name, prog)
    avg: tuple[float, str] | None = None
    for req in requirements:
        if req.min_gcse_count:
            g = req.min_gcse_grade or 4
            if g not in counts or req.min_gcse_count > counts[g][0]:
                counts[g] = (req.min_gcse_count, req.programme)
        for subj, g in req.subject_minimums.items():
            key = _area(subj) or _norm(subj)
            if key not in subjects or g > subjects[key][0]:
                subjects[key] = (g, subj, req.programme)
        if req.min_average_points and (
                avg is None or req.min_average_points > avg[0]):
            avg = (req.min_average_points, req.programme)
    out: list[dict[str, Any]] = []
    for g, (n, prog) in sorted(counts.items(), reverse=True):
        out.append({"kind": "gcse_count", "min_grade": g, "min_count": n,
                    "source_programme": prog})
    for g, subj, prog in subjects.values():
        out.append({"kind": "subject_grade", "subject": subj, "min_grade": g,
                    "source_programme": prog})
    if avg:
        out.append({"kind": "average_points", "min_points": avg[0],
                    "source_programme": avg[1]})
    return out


def generate_conditions(applicant_id: str, *, replace: bool = True
                        ) -> list[OfferCondition]:
    """Build conditional-offer rows from the entry requirements.

    ``replace`` drops the generated rows first (hand-added "other" rows
    are always kept). The applicant's offer-conditions text is rebuilt.
    """
    init_db()
    if _adm.get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    proposed = _proposed(applicant_id)
    with _connect() as conn:
        if replace:
            conn.execute("DELETE FROM admissions_offer_conditions WHERE "
                         "applicant_id = ? AND kind != 'other'",
                         (applicant_id,))
        existing = {(r["kind"], _norm(r["subject"]), r["min_grade"],
                     r["min_count"], r["min_points"]) for r in conn.execute(
            "SELECT * FROM admissions_offer_conditions WHERE applicant_id = ?",
            (applicant_id,)).fetchall()}
        for order, p in enumerate(proposed):
            key = (p["kind"], _norm(p.get("subject")), p.get("min_grade"),
                   p.get("min_count"), p.get("min_points"))
            if key in existing:
                continue
            conn.execute(
                """INSERT INTO admissions_offer_conditions
                       (applicant_id, kind, subject, min_grade, min_count,
                        min_points, description, source_programme, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (applicant_id, p["kind"], p.get("subject"),
                 p.get("min_grade"), p.get("min_count"), p.get("min_points"),
                 _describe(p["kind"], p.get("subject"), p.get("min_grade"),
                           p.get("min_count"), p.get("min_points")),
                 p["source_programme"], order))
        _adm._log_event(conn, applicant_id,
                        f"Offer conditions generated from entry requirements "
                        f"({len(proposed)} rule(s))", kind="offer")
        conn.commit()
    sync_conditions_text(applicant_id)
    return list_conditions(applicant_id)


def add_condition(applicant_id: str, *, kind: str = "other",
                  description: str | None = None, subject: str | None = None,
                  min_grade: Any = None, min_count: Any = None,
                  min_points: Any = None) -> OfferCondition:
    """Add one condition by hand (structured or free text)."""
    init_db()
    if _adm.get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    p = _validate_condition(kind, description, subject, min_grade,
                            min_count, min_points)
    with _connect() as conn:
        n = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM "
            "admissions_offer_conditions WHERE applicant_id = ?",
            (applicant_id,)).fetchone()["n"]
        cur = conn.execute(
            """INSERT INTO admissions_offer_conditions
                   (applicant_id, kind, subject, min_grade, min_count,
                    min_points, description, source_programme, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Added by hand', ?)""",
            (applicant_id, p["kind"], p["subject"], p["min_grade"],
             p["min_count"], p["min_points"], p["description"], n))
        _adm._log_event(conn, applicant_id,
                        f"Offer condition added: {p['description']}",
                        kind="offer")
        conn.commit()
        cid = cur.lastrowid
    sync_conditions_text(applicant_id)
    out = get_condition(cid)
    assert out is not None
    return out


def _validate_condition(kind: str, description: str | None,
                        subject: str | None, min_grade: Any,
                        min_count: Any, min_points: Any) -> dict[str, Any]:
    if kind not in CONDITION_KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(CONDITION_KINDS)}")
    out: dict[str, Any] = {"kind": kind, "subject": None, "min_grade": None,
                           "min_count": None, "min_points": None}
    if kind == "gcse_count":
        out["min_grade"] = _int_grade(min_grade, "Grade") or 4
        try:
            out["min_count"] = int(min_count)
        except (TypeError, ValueError):
            raise ValidationError("Number of GCSEs is required") from None
        if not 1 <= out["min_count"] <= 15:
            raise ValidationError("Number of GCSEs must be between 1 and 15")
    elif kind == "subject_grade":
        out["subject"] = (subject or "").strip() or None
        if not out["subject"]:
            raise ValidationError("Subject is required")
        out["min_grade"] = _int_grade(min_grade, "Grade")
        if out["min_grade"] is None:
            raise ValidationError("Grade is required")
    elif kind == "average_points":
        try:
            out["min_points"] = round(float(min_points), 2)
        except (TypeError, ValueError):
            raise ValidationError("Average point score is required") from None
        if not 0 < out["min_points"] <= 9:
            raise ValidationError("Average point score must be between 0 and 9")
    desc = (description or "").strip()
    if not desc:
        desc = _describe(kind, out["subject"], out["min_grade"],
                         out["min_count"], out["min_points"])
    if not desc:
        raise ValidationError("Description is required")
    if len(desc) > 300:
        raise ValidationError("Description is too long")
    out["description"] = desc
    return out


def update_condition(condition_id: int, **changes: Any) -> OfferCondition:
    """Edit a condition (description, subject, grade, count, points)."""
    c = get_condition(condition_id)
    if c is None:
        raise ValidationError(f"No condition #{condition_id}")
    merged = {
        "kind": changes.get("kind", c.kind),
        "description": changes.get("description", c.description),
        "subject": changes.get("subject", c.subject),
        "min_grade": changes.get("min_grade", c.min_grade),
        "min_count": changes.get("min_count", c.min_count),
        "min_points": changes.get("min_points", c.min_points),
    }
    rule_changed = any(k in changes for k in
                       ("kind", "subject", "min_grade", "min_count",
                        "min_points"))
    if rule_changed and "description" not in changes:
        merged["description"] = None      # regenerate from the new rule
    p = _validate_condition(merged["kind"], merged["description"],
                            merged["subject"], merged["min_grade"],
                            merged["min_count"], merged["min_points"])
    with _connect() as conn:
        conn.execute(
            """UPDATE admissions_offer_conditions SET kind = ?, subject = ?,
                   min_grade = ?, min_count = ?, min_points = ?,
                   description = ?, outcome = 'Pending',
                   outcome_detail = NULL, evaluated_at = NULL
               WHERE condition_id = ?""",
            (p["kind"], p["subject"], p["min_grade"], p["min_count"],
             p["min_points"], p["description"], condition_id))
        _adm._log_event(conn, c.applicant_id,
                        f"Offer condition edited: {p['description']}",
                        kind="offer")
        conn.commit()
    sync_conditions_text(c.applicant_id)
    out = get_condition(condition_id)
    assert out is not None
    return out


def set_manual_outcome(condition_id: int, outcome: str | None, *,
                       by: str | None = None) -> OfferCondition:
    """Staff judgement on a condition (needed for free-text ones)."""
    c = get_condition(condition_id)
    if c is None:
        raise ValidationError(f"No condition #{condition_id}")
    if outcome and outcome not in MANUAL_OUTCOMES:
        raise ValidationError(f"Outcome must be one of: "
                              f"{', '.join(MANUAL_OUTCOMES)}")
    with _connect() as conn:
        conn.execute("UPDATE admissions_offer_conditions SET manual_outcome "
                     "= ? WHERE condition_id = ?",
                     (outcome or None, condition_id))
        _adm._log_event(conn, c.applicant_id,
                        f"Condition '{c.description}' marked "
                        f"{outcome or 'automatic'} by {by or _username() or '?'}",
                        kind="offer")
        conn.commit()
    out = get_condition(condition_id)
    assert out is not None
    return out


def delete_condition(condition_id: int) -> bool:
    c = get_condition(condition_id)
    if c is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM admissions_offer_conditions "
                     "WHERE condition_id = ?", (condition_id,))
        _adm._log_event(conn, c.applicant_id,
                        f"Offer condition removed: {c.description}",
                        kind="offer")
        conn.commit()
    sync_conditions_text(c.applicant_id)
    return True


def conditions_text(applicant_id: str) -> str:
    return "; ".join(c.description for c in list_conditions(applicant_id))


def sync_conditions_text(applicant_id: str) -> None:
    """Rewrite the applicant's free-text conditions from the rows."""
    text = conditions_text(applicant_id) or None
    with _connect() as conn:
        conn.execute("UPDATE admissions_applicants SET offer_conditions = ?, "
                     "updated_at = datetime('now') WHERE applicant_id = ?",
                     (text, applicant_id))
        conn.commit()


def make_structured_offer(applicant_id: str, *,
                          offer_type: str = "Conditional",
                          decided_by: str | None = None,
                          regenerate: bool = True,
                          expiry: str | None = None) -> _adm.Applicant:
    """Make an offer whose conditions are the structured rows.

    A conditional offer (re)generates its rows from the entry
    requirements unless ``regenerate`` is False; an unconditional one
    keeps any rows for reference but carries no conditions text.
    """
    if offer_type == "Conditional":
        if regenerate or not list_conditions(applicant_id):
            generate_conditions(applicant_id)
        text = conditions_text(applicant_id) or None
    else:
        text = None
    out = _adm.make_offer(applicant_id, offer_type=offer_type,
                          conditions=text, decided_by=decided_by)
    if expiry is not None:
        out = _adm.set_offer_expiry(applicant_id, expiry or None)
    return out


# ── Evaluation ─────────────────────────────────────────────────────

def _best_for(subject: str, results: list[GCSE]) -> GCSE | None:
    best: GCSE | None = None
    for r in results:
        if r.kind == "GCSE short course":
            continue
        if subject_matches(subject, r.subject):
            if best is None or (r.points or 0) > (best.points or 0):
                best = r
    return best


def _check(c: OfferCondition, results: list[GCSE]) -> tuple[str, str]:
    if c.kind == "other":
        return "Manual", "Needs a staff decision"
    if not results:
        return "Pending", "No results recorded"
    full = [r for r in results if r.kind != "GCSE short course"]
    if c.kind == "subject_grade":
        best = _best_for(c.subject or "", results)
        if best is None:
            return "Not met", f"No GCSE {c.subject} result"
        pts = best.points or 0
        need = float(c.min_grade or 0)
        if pts >= need:
            return "Met", f"{best.subject} {best.grade}"
        if pts >= need - 1:
            return "Near miss", f"{best.subject} {best.grade} (needed {c.min_grade})"
        return "Not met", f"{best.subject} {best.grade} (needed {c.min_grade})"
    if c.kind == "gcse_count":
        need_n, g = int(c.min_count or 0), float(c.min_grade or 4)
        at = sum(1 for r in full if (r.points or 0) >= g)
        if at >= need_n:
            return "Met", f"{at} at grade {c.min_grade}+"
        one_lower = sum(1 for r in full if (r.points or 0) >= g - 1)
        if at == need_n - 1 or one_lower >= need_n:
            return "Near miss", (f"{at} at grade {c.min_grade}+ "
                                 f"(needed {need_n})")
        return "Not met", f"{at} at grade {c.min_grade}+ (needed {need_n})"
    if c.kind == "average_points":
        weights = {"GCSE": 1.0, "IGCSE": 1.0, "GCSE short course": 0.5}
        total = sum(weights.get(r.kind, 1.0) for r in results
                    if r.points is not None)
        if not total:
            return "Pending", "No scoreable results"
        avg = sum((r.points or 0) * weights.get(r.kind, 1.0)
                  for r in results if r.points is not None) / total
        need = float(c.min_points or 0)
        if avg >= need - 1e-9:
            return "Met", f"Average {avg:.2f}"
        # One grade higher in one full GCSE raises the average by 1/total.
        if avg + 1.0 / total >= need - 1e-9:
            return "Near miss", f"Average {avg:.2f} (needed {need:g})"
        return "Not met", f"Average {avg:.2f} (needed {need:g})"
    return "Manual", "Unknown condition type"


@dataclass
class _GivenResult:
    """A GCSE result passed in as plain data (not an applicant's record)."""
    subject: str
    grade: str
    kind: str

    @property
    def points(self) -> float | None:
        return grade_points(self.grade)


def course_eligibility(results: list[dict[str, Any]], courses: list[str]
                       ) -> list[dict[str, Any]]:
    """Whether *results* (``{subject, grade, qualification}`` dicts) meet the
    entry requirements of each of *courses*: the college-wide minimum
    (:data:`GENERAL_PROGRAMME`) plus the course's own. Nothing is stored.

    Each item: ``course``, ``outcome`` (Met / Near miss / Not met / Pending;
    Met when nothing is required), ``requirements`` (what is asked, in words)
    and ``checks`` (``{requirement, outcome, detail, programme}``).
    """
    init_db()
    given = []
    for r in results or []:
        subject = (r.get("subject") or "").strip()
        grade = str(r.get("grade") or "").strip().upper()
        kind = (r.get("qualification") or "GCSE").strip()
        if subject and grade_points(grade) is not None:
            given.append(_GivenResult(subject, grade,
                                      kind if kind in GCSE_KINDS else "GCSE"))
    by_name = {_norm(r.programme): r for r in list_requirements()}  # one read
    general = by_name.get(_norm(GENERAL_PROGRAMME))
    out = []
    for course in courses:
        reqs = [r for r in (general, by_name.get(_norm(course))) if r is not None]
        checks = []
        for i, d in enumerate(_merge(reqs)):
            c = OfferCondition(
                condition_id=0, applicant_id="", kind=d["kind"], subject=d.get("subject"),
                min_grade=d.get("min_grade"), min_count=d.get("min_count"),
                min_points=d.get("min_points"),
                description=_describe(d["kind"], d.get("subject"), d.get("min_grade"),
                                      d.get("min_count"), d.get("min_points")),
                source_programme=d.get("source_programme"), sort_order=i,
                outcome="Pending", outcome_detail=None, manual_outcome=None,
                evaluated_at=None)
            outcome, detail = _check(c, given)  # type: ignore[arg-type]
            checks.append({"requirement": c.description, "outcome": outcome,
                           "detail": detail, "programme": c.source_programme})
        found = {x["outcome"] for x in checks}
        overall = ("Not met" if "Not met" in found else "Pending" if "Pending" in found
                   else "Near miss" if "Near miss" in found else "Met")
        out.append({"course": course, "outcome": overall,
                    "requirements": [x["requirement"] for x in checks], "checks": checks})
    return out


def evaluate(applicant_id: str, *, result_type: str = "Actual",
             save: bool = True) -> Evaluation:
    """Check every condition against the applicant's GCSE results.

    ``result_type`` "Actual" uses confirmed results (results day);
    "Predicted" gives an early read. Outcomes are stored on the rows
    when ``save`` is True. Overall: Met when every condition is met,
    Not met when any is not met, Near miss when the only shortfalls
    are near misses, Pending when there are no results or a free-text
    condition still needs a staff decision.
    """
    init_db()
    if result_type not in RESULT_TYPES:
        raise ValidationError(f"Result type must be one of: "
                              f"{', '.join(RESULT_TYPES)}")
    results = list_gcses(applicant_id, result_type=result_type)
    conds = list_conditions(applicant_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    evaluated: list[OfferCondition] = []
    with _connect() as conn:
        for c in conds:
            outcome, detail = _check(c, results)
            if save:
                conn.execute(
                    "UPDATE admissions_offer_conditions SET outcome = ?, "
                    "outcome_detail = ?, evaluated_at = ? "
                    "WHERE condition_id = ?",
                    (outcome, f"[{result_type}] {detail}", now,
                     c.condition_id))
            c.outcome, c.outcome_detail, c.evaluated_at = (
                outcome, f"[{result_type}] {detail}", now)
            evaluated.append(c)
        if save and conds:
            conn.commit()
    effective = [c.effective_outcome for c in evaluated]
    if not results and not all(e in MANUAL_OUTCOMES for e in effective):
        overall = "Pending"
    elif any(e == "Not met" for e in effective):
        overall = "Not met"
    elif any(e in ("Pending", "Manual") for e in effective):
        overall = "Pending"
    elif any(e == "Near miss" for e in effective):
        overall = "Near miss"
    else:
        overall = "Met"
    return Evaluation(applicant_id=applicant_id, result_type=result_type,
                      overall=overall, conditions=evaluated,
                      results_used=len(results))
