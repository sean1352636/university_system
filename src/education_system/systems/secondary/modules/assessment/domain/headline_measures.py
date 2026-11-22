"""Attainment 8, Progress 8 and the headline measures.

Kept from the old system: one **Attainment 8** record per pupil per
academic year per source (Estimated / Predicted / Actual), holding the
grade in each slot (English, Maths, three EBacc, three Open), the total and
the A8; and one **Progress 8** record per pupil per year holding the KS2
prior attainment, the expected A8, the A8 (pulled from the A8 records,
Actual first) and the P8. Both can be entered by hand, edited, listed by
year group / academic year / source, summarised and deleted; P8 can
re-pull its A8 ("Refresh A8").

What changed:

* **Calculated from the school's own data** instead of typed in: Actual
  from released exam results (never grades still under embargo), Predicted
  from an assessment point (predicted grade, or working-at), Estimated from
  the latest mock exams, and a new **Target** source from target grades.
  A record entered by hand is marked so and is never overwritten by a
  recalculation.
* **The DfE slot rules.** English counts twice when the pupil has both
  English language and English literature (the better grade; the other can
  fill an Open slot), once when they have only one. Maths always counts
  twice. Three EBacc slots take the best sciences (combined science fills
  two), computer science, history, geography and languages - the subjects'
  EBacc category; three Open slots take the best of everything left. An
  empty slot scores 0 and the record still counts (the old code voided a
  record with a blank slot). GCSE 9-1 grades score 9-1, U 0; combined
  "6-5" scores 5.5 in each of two slots; BTEC Level 2 scores Distinction*
  8.5, Distinction 7, Merit 5.5, Pass 4. Short-course GCSEs and subjects
  with no points scale aren't counted (and are listed as such).
* **The A8 score is out of 90** (the total of the ten weighted slots, as the
  DfE reports it). The old "A8" (total / 10) is shown as the average grade.
* **Progress 8 = (A8 - expected A8) / 10**, with the expected A8 read from
  the DfE estimates the school enters for that year, by the pupil's KS2
  prior attainment (the average of their KS2 reading and maths scaled
  scores, 80-120 - or the one they have). The old code took KS2 as 0-6 and
  a made-up expected-A8 table. With element estimates entered, the English,
  Maths, EBacc and Open P8 elements are worked out too. A pupil with no KS2
  data has no P8 (as in the performance tables).
* **Headline measures** for a year group and source: pupils, average A8,
  average P8, English and maths at 4+ and 5+, EBacc entry - for everyone and
  split by disadvantaged (free school meals), SEN, gender and EAL, with the
  disadvantaged gap.

Who: anyone on the staff can look; the data manager
(:data:`HEADLINE_MEASURE_EDITORS`) enters KS2 data and estimates, calculates
and edits records. Every change is kept in ``headline_audit`` and the
activity log (ids only, no grades or names).
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import HEADLINE_MEASURE_EDITORS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

#: Old sources first; Target is new.
SOURCES: tuple[str, ...] = ("Estimated", "Predicted", "Actual", "Target")
DEFAULT_SOURCE = "Estimated"
#: The order a Progress 8 record looks for an A8 record.
A8_PREFERENCE: tuple[str, ...] = ("Actual", "Predicted", "Estimated", "Target")
METHODS: tuple[str, ...] = ("Calculated", "Entered")
SLOTS: tuple[str, ...] = ("english_grade", "maths_grade", "ebacc1_grade", "ebacc2_grade",
                          "ebacc3_grade", "open1_grade", "open2_grade", "open3_grade")
SLOT_LABELS: dict[str, str] = {
    "english_grade": "English", "maths_grade": "Maths", "ebacc1_grade": "EBacc 1",
    "ebacc2_grade": "EBacc 2", "ebacc3_grade": "EBacc 3", "open1_grade": "Open 1",
    "open2_grade": "Open 2", "open3_grade": "Open 3"}
GCSE_POINTS: dict[str, float] = {str(n): float(n) for n in range(1, 10)} | {"U": 0.0,
                                                                              "X": 0.0}
BTEC_POINTS: dict[str, float] = {"D*": 8.5, "D": 7.0, "M": 5.5, "P": 4.0, "U": 0.0}
EBACC_SLOT_CATEGORIES = frozenset({"Science", "Humanities", "Languages"})
KS2_MIN, KS2_MAX = 80, 120
KS2_SOURCES: tuple[str, ...] = ("CTF", "Primary school", "DfE", "Entered")
ELEMENTS: tuple[str, ...] = ("english", "maths", "ebacc", "open")
#: Slots per element, to turn an element difference into a P8 element score.
ELEMENT_SLOTS = {"english": 2, "maths": 2, "ebacc": 3, "open": 3}
_YEAR_RE = re.compile(r"^(\d{4})/(\d{2})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ks2_prior_attainment (
    pupil_id        INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    reading_scaled  INTEGER CHECK (reading_scaled IS NULL OR reading_scaled BETWEEN 80 AND 120),
    maths_scaled    INTEGER CHECK (maths_scaled IS NULL OR maths_scaled BETWEEN 80 AND 120),
    source          TEXT NOT NULL DEFAULT 'Entered',
    notes           TEXT,
    updated_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS p8_estimates (
    academic_year     TEXT NOT NULL,
    ks2_from          REAL NOT NULL,
    expected_a8       REAL NOT NULL CHECK (expected_a8 BETWEEN 0 AND 90),
    expected_english  REAL,
    expected_maths    REAL,
    expected_ebacc    REAL,
    expected_open     REAL,
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (academic_year, ks2_from)
);
CREATE TABLE IF NOT EXISTS attainment8_records (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year  TEXT NOT NULL,
    record_source  TEXT NOT NULL CHECK (record_source IN
                   ('Estimated', 'Predicted', 'Actual', 'Target')),
    english_grade  TEXT,
    maths_grade    TEXT,
    ebacc1_grade   TEXT,
    ebacc2_grade   TEXT,
    ebacc3_grade   TEXT,
    open1_grade    TEXT,
    open2_grade    TEXT,
    open3_grade    TEXT,
    english_points REAL NOT NULL DEFAULT 0,
    maths_points   REAL NOT NULL DEFAULT 0,
    ebacc_points   REAL NOT NULL DEFAULT 0,
    open_points    REAL NOT NULL DEFAULT 0,
    total_points   REAL NOT NULL DEFAULT 0,
    english_double INTEGER NOT NULL DEFAULT 1,
    ebacc_entered  INTEGER,
    slot_detail    TEXT,
    method         TEXT NOT NULL DEFAULT 'Entered' CHECK (method IN ('Calculated', 'Entered')),
    based_on       TEXT,
    notes          TEXT,
    recorded_by    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year, record_source)
);
CREATE INDEX IF NOT EXISTS ix_a8_year ON attainment8_records (academic_year, record_source);
CREATE TABLE IF NOT EXISTS progress8_records (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year  TEXT NOT NULL,
    ks2_prior      REAL NOT NULL CHECK (ks2_prior BETWEEN 80 AND 120),
    expected_a8    REAL NOT NULL CHECK (expected_a8 BETWEEN 0 AND 90),
    expected_from  TEXT NOT NULL DEFAULT 'Entered',
    attainment_8   REAL CHECK (attainment_8 IS NULL OR attainment_8 BETWEEN 0 AND 90),
    a8_source      TEXT,
    progress_8     REAL,
    p8_english     REAL,
    p8_maths       REAL,
    p8_ebacc       REAL,
    p8_open        REAL,
    method         TEXT NOT NULL DEFAULT 'Entered' CHECK (method IN ('Calculated', 'Entered')),
    notes          TEXT,
    recorded_by    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year)
);
CREATE TABLE IF NOT EXISTS headline_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    area       TEXT NOT NULL,
    action     TEXT NOT NULL,
    pupil_id   INTEGER,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("headline_measures", _SCHEMA)


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KS2:
    pupil_id: int
    reading_scaled: int | None
    maths_scaled: int | None
    source: str
    notes: str | None
    updated_by: str | None
    updated_at: str

    @property
    def prior(self) -> float | None:
        """Average of the scaled scores the pupil has (None if neither)."""
        have = [s for s in (self.reading_scaled, self.maths_scaled) if s is not None]
        return round(sum(have) / len(have), 1) if have else None


@dataclass(frozen=True)
class Estimate:
    academic_year: str
    ks2_from: float
    expected_a8: float
    expected_english: float | None
    expected_maths: float | None
    expected_ebacc: float | None
    expected_open: float | None


@dataclass(frozen=True)
class A8Record:
    record_id: int
    pupil_id: int
    academic_year: str
    record_source: str
    english_grade: str | None
    maths_grade: str | None
    ebacc1_grade: str | None
    ebacc2_grade: str | None
    ebacc3_grade: str | None
    open1_grade: str | None
    open2_grade: str | None
    open3_grade: str | None
    english_points: float
    maths_points: float
    ebacc_points: float
    open_points: float
    total_points: float
    english_double: bool
    ebacc_entered: bool | None
    slot_detail: list[dict[str, Any]]
    method: str
    based_on: str | None
    notes: str | None
    recorded_by: str | None
    created_at: str
    updated_at: str
    admission_no: str = ""
    pupil_name: str = ""
    year_group: int = 0

    @property
    def attainment_8(self) -> float:
        """The A8 score (out of 90)."""
        return self.total_points

    @property
    def average_grade(self) -> float:
        """A8 / 10 (what the old screen called "A8")."""
        return round(self.total_points / 10, 2)

    def grade(self, slot: str) -> str | None:
        return getattr(self, slot)


@dataclass(frozen=True)
class P8Record:
    record_id: int
    pupil_id: int
    academic_year: str
    ks2_prior: float
    expected_a8: float
    expected_from: str
    attainment_8: float | None
    a8_source: str | None
    progress_8: float | None
    p8_english: float | None
    p8_maths: float | None
    p8_ebacc: float | None
    p8_open: float | None
    method: str
    notes: str | None
    recorded_by: str | None
    created_at: str
    updated_at: str
    admission_no: str = ""
    pupil_name: str = ""
    year_group: int = 0


def _pupil_bits(r) -> dict[str, Any]:
    return {"admission_no": r["admission_no"] or "",
            "pupil_name": f"{r['legal_last_name']}, {r['preferred_name'] or r['legal_first_name']}",
            "year_group": r["year_group"] or 0}


_JOIN = (" JOIN pupils p ON p.pupil_id = r.pupil_id")
_PCOLS = ", p.admission_no, p.legal_last_name, p.legal_first_name, p.preferred_name, p.year_group"


def _a8(r) -> A8Record:
    d = {k: r[k] for k in A8Record.__dataclass_fields__ if k not in
         ("admission_no", "pupil_name", "year_group")}
    d["english_double"] = bool(d["english_double"])
    d["ebacc_entered"] = None if d["ebacc_entered"] is None else bool(d["ebacc_entered"])
    d["slot_detail"] = json.loads(d["slot_detail"] or "[]")
    return A8Record(**d, **_pupil_bits(r))


def _p8(r) -> P8Record:
    d = {k: r[k] for k in P8Record.__dataclass_fields__ if k not in
         ("admission_no", "pupil_name", "year_group")}
    return P8Record(**d, **_pupil_bits(r))


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in HEADLINE_MEASURE_EDITORS


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(f"headline.{action}", target=target, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the data manager can change Attainment 8 / Progress 8 "
                               "data.")


def _audit(conn, area: str, action: str, actor: Principal, pupil_id: int | None = None,
           **detail: Any) -> None:
    conn.execute("INSERT INTO headline_audit (area, action, pupil_id, detail, actor) VALUES "
                 "(?, ?, ?, ?, ?)", (area, action, pupil_id,
                                     json.dumps(detail, default=str) if detail else None,
                                     actor.username or "unknown"))


def history(*, pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM headline_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [{"at": r["at"], "area": r["area"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _academic_year(value: Any, problems: list[str]) -> str | None:
    y = str(value or "").strip()
    m = _YEAR_RE.match(y)
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        problems.append("Academic year must look like 2026/27")
        return None
    return y


def _pupil(ref: Any) -> P.Pupil:
    p = P.get_pupil(int(ref)) if str(ref).isdigit() and P.get_pupil(int(ref)) else \
        P.find_by_reference(str(ref or ""))
    if p is None:
        raise NotFound(f"No pupil {ref}")
    return p


def _number(value: Any, label: str, problems: list[str], *, low: float, high: float,
            required: bool = False, whole: bool = False) -> float | None:
    if value in (None, ""):
        if required:
            problems.append(f"{label} is required")
        return None
    try:
        n = float(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if whole and n != int(n):
        problems.append(f"{label} must be a whole number")
        return None
    if not low <= n <= high:
        problems.append(f"{label} must be between {low:g} and {high:g}")
        return None
    return int(n) if whole else n


def _text(value: Any, limit: int = 500) -> str | None:
    t = str(value or "").strip()
    return t[:limit] or None


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    """Rows of a CSV with lower-case headers; a file that can't be read is a
    ValidationError, not a crash."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                    for row in csv.DictReader(fh)]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise ValidationError([f"Couldn't read {Path(path).name}: "
                               f"{getattr(e, 'strerror', None) or e}"]) from None


def _safe(value: Any) -> str:
    """CSV cell that can't start a spreadsheet formula."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ── KS2 prior attainment ─────────────────────────────────────────────

def get_ks2(pupil_id: int) -> KS2 | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM ks2_prior_attainment WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    return KS2(**{k: r[k] for k in KS2.__dataclass_fields__}) if r else None


def ks2_map() -> dict[int, KS2]:
    with database.connect() as conn:
        return {r["pupil_id"]: KS2(**{k: r[k] for k in KS2.__dataclass_fields__})
                for r in conn.execute("SELECT * FROM ks2_prior_attainment")}


def ks2_list(*, year_group: int | None = None, missing_only: bool = False,
             search: str | None = None) -> list[tuple[P.Pupil, KS2 | None]]:
    have = ks2_map()
    out = [(p, have.get(p.pupil_id)) for p in P.list_pupils(year_group=year_group,
                                                            search=search)]
    if missing_only:
        out = [(p, k) for p, k in out if k is None or k.prior is None]
    return out


def _clean_ks2(data: dict[str, Any], problems: list[str], label: str = "") -> dict[str, Any]:
    out = {"reading_scaled": _number(data.get("reading_scaled"), f"{label}KS2 reading",
                                     problems, low=KS2_MIN, high=KS2_MAX, whole=True),
           "maths_scaled": _number(data.get("maths_scaled"), f"{label}KS2 maths", problems,
                                   low=KS2_MIN, high=KS2_MAX, whole=True),
           "notes": _text(data.get("notes"))}
    src = str(data.get("source") or "Entered").strip()
    match = next((s for s in KS2_SOURCES if s.lower() == src.lower()), None)
    if match is None:
        problems.append(f"{label}Source must be one of {', '.join(KS2_SOURCES)}")
    out["source"] = match or "Entered"
    if out["reading_scaled"] is None and out["maths_scaled"] is None and not problems:
        problems.append(f"{label}Give a KS2 reading or maths scaled score ({KS2_MIN}-{KS2_MAX})"
                        " - or clear the record")
    return out


def _write_ks2(conn, pupil_id: int, c: dict[str, Any], actor: Principal) -> None:
    conn.execute(
        "INSERT INTO ks2_prior_attainment (pupil_id, reading_scaled, maths_scaled, source, "
        "notes, updated_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (pupil_id) DO UPDATE SET "
        "reading_scaled = excluded.reading_scaled, maths_scaled = excluded.maths_scaled, "
        "source = excluded.source, notes = excluded.notes, updated_by = excluded.updated_by, "
        "updated_at = datetime('now')",
        (pupil_id, c["reading_scaled"], c["maths_scaled"], c["source"], c["notes"],
         actor.username))
    _audit(conn, "ks2", "set", actor, pupil_id, source=c["source"])


def set_ks2(pupil_id: int, data: dict[str, Any], *, actor: Principal) -> KS2:
    p = _pupil(pupil_id)
    _require(actor, "ks2_set", p.admission_no)
    problems: list[str] = []
    c = _clean_ks2(data, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        _write_ks2(conn, p.pupil_id, c, actor)
    activity_log.record("headline.ks2_set", target=p.admission_no, principal=actor)
    return get_ks2(p.pupil_id)  # type: ignore[return-value]


def clear_ks2(pupil_id: int, *, actor: Principal) -> bool:
    p = _pupil(pupil_id)
    _require(actor, "ks2_clear", p.admission_no)
    with database.connect() as conn:
        n = conn.execute("DELETE FROM ks2_prior_attainment WHERE pupil_id = ?",
                         (p.pupil_id,)).rowcount
        if n:
            _audit(conn, "ks2", "clear", actor, p.pupil_id)
    activity_log.record("headline.ks2_clear", target=p.admission_no, principal=actor)
    return bool(n)


def import_ks2(path: str | Path, *, actor: Principal) -> dict[str, int]:
    """CSV with ``admission_no`` (or ``upn``), ``reading`` and ``maths``
    (scaled scores), optional ``source``. All rows or none."""
    _require(actor, "ks2_import")
    problems: list[str] = []
    todo: list[tuple[int, dict[str, Any]]] = []
    seen: set[int] = set()
    for n, row in enumerate(_read_csv(path), start=2):
        ref = row.get("admission_no") or row.get("upn") or ""
        p = P.find_by_reference(ref) if ref else None
        if p is None:
            problems.append(f"Row {n}: no pupil {ref or '(blank)'}")
            continue
        if p.pupil_id in seen:
            problems.append(f"Row {n}: {p.admission_no} is in the file twice")
            continue
        seen.add(p.pupil_id)
        c = _clean_ks2({"reading_scaled": row.get("reading") or row.get("reading_scaled"),
                        "maths_scaled": row.get("maths") or row.get("maths_scaled"),
                        "source": row.get("source") or "CTF"}, problems, f"Row {n}: ")
        todo.append((p.pupil_id, c))
    if problems:
        activity_log.record("headline.ks2_import", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        for pid, c in todo:
            _write_ks2(conn, pid, c, actor)
    activity_log.record("headline.ks2_import", principal=actor, rows=len(todo))
    return {"imported": len(todo)}


# ── DfE Progress 8 estimates ─────────────────────────────────────────

def estimates(academic_year: str) -> list[Estimate]:
    with database.connect() as conn:
        return [Estimate(**{k: r[k] for k in Estimate.__dataclass_fields__})
                for r in conn.execute("SELECT * FROM p8_estimates WHERE academic_year = ? "
                                      "ORDER BY ks2_from", (academic_year,))]


def estimate_years() -> list[str]:
    with database.connect() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT academic_year FROM p8_estimates "
                                           "ORDER BY academic_year DESC")]


def estimate_for(academic_year: str, ks2_prior: float | None,
                 table: list[Estimate] | None = None) -> Estimate | None:
    """The estimate row for a KS2 prior attainment: the highest band
    starting at or below it (None without KS2 or without estimates)."""
    if ks2_prior is None:
        return None
    rows = table if table is not None else estimates(academic_year)
    hit = None
    for e in rows:
        if e.ks2_from <= ks2_prior + 1e-9:
            hit = e
    return hit or (rows[0] if rows and ks2_prior < rows[0].ks2_from else None)


def _clean_estimate(data: dict[str, Any], problems: list[str], label: str = ""
                    ) -> dict[str, Any]:
    out = {"ks2_from": _number(data.get("ks2_from"), f"{label}KS2 from", problems,
                               low=KS2_MIN - 20, high=KS2_MAX, required=True),
           "expected_a8": _number(data.get("expected_a8"), f"{label}Expected A8", problems,
                                  low=0, high=90, required=True)}
    for el in ELEMENTS:
        out[f"expected_{el}"] = _number(data.get(f"expected_{el}"),
                                        f"{label}Expected {el}", problems, low=0,
                                        high=10.0 * ELEMENT_SLOTS[el])
    return out


def set_estimate(academic_year: str, data: dict[str, Any], *, actor: Principal) -> Estimate:
    _require(actor, "estimate_set")
    problems: list[str] = []
    year = _academic_year(academic_year, problems)
    c = _clean_estimate(data, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        _write_estimate(conn, year, c, actor)  # type: ignore[arg-type]
        _audit(conn, "estimates", "set", actor, year=year, ks2_from=c["ks2_from"])
    activity_log.record("headline.estimate_set", target=year, principal=actor)
    return next(e for e in estimates(year) if abs(e.ks2_from - c["ks2_from"]) < 1e-9)  # type: ignore[arg-type]


def _write_estimate(conn, year: str, c: dict[str, Any], actor: Principal) -> None:
    conn.execute(
        "INSERT INTO p8_estimates (academic_year, ks2_from, expected_a8, expected_english, "
        "expected_maths, expected_ebacc, expected_open, updated_by) VALUES (?, ?, ?, ?, ?, ?, "
        "?, ?) ON CONFLICT (academic_year, ks2_from) DO UPDATE SET expected_a8 = "
        "excluded.expected_a8, expected_english = excluded.expected_english, expected_maths = "
        "excluded.expected_maths, expected_ebacc = excluded.expected_ebacc, expected_open = "
        "excluded.expected_open, updated_by = excluded.updated_by, updated_at = datetime('now')",
        (year, c["ks2_from"], c["expected_a8"], c["expected_english"], c["expected_maths"],
         c["expected_ebacc"], c["expected_open"], actor.username))


def delete_estimate(academic_year: str, ks2_from: float, *, actor: Principal) -> bool:
    _require(actor, "estimate_delete")
    with database.connect() as conn:
        n = conn.execute("DELETE FROM p8_estimates WHERE academic_year = ? AND "
                         "abs(ks2_from - ?) < 1e-9", (academic_year, float(ks2_from))).rowcount
        if n:
            _audit(conn, "estimates", "delete", actor, year=academic_year, ks2_from=ks2_from)
    activity_log.record("headline.estimate_delete", target=academic_year, principal=actor)
    return bool(n)


def import_estimates(academic_year: str, path: str | Path, *, actor: Principal,
                     replace: bool = True) -> dict[str, int]:
    """CSV of the DfE estimates: ``ks2_from``, ``expected_a8`` and optional
    ``expected_english`` / ``_maths`` / ``_ebacc`` / ``_open``. All rows or
    none; *replace* clears the year first."""
    _require(actor, "estimate_import")
    problems: list[str] = []
    year = _academic_year(academic_year, problems)
    rows: list[dict[str, Any]] = []
    seen: set[float] = set()
    for n, row in enumerate(_read_csv(path), start=2):
        c = _clean_estimate(row, problems, f"Row {n}: ")
        if c["ks2_from"] is not None and c["ks2_from"] in seen:
            problems.append(f"Row {n}: KS2 {c['ks2_from']:g} is in the file twice")
        seen.add(c["ks2_from"])
        rows.append(c)
    if not rows and not problems:
        problems.append("The file has no estimate rows")
    if problems:
        activity_log.record("headline.estimate_import", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        if replace:
            conn.execute("DELETE FROM p8_estimates WHERE academic_year = ?", (year,))
        for c in rows:
            _write_estimate(conn, year, c, actor)  # type: ignore[arg-type]
        _audit(conn, "estimates", "import", actor, year=year, rows=len(rows))
    activity_log.record("headline.estimate_import", target=year, principal=actor,
                        rows=len(rows))
    return {"imported": len(rows)}


def copy_estimates(from_year: str, to_year: str, *, actor: Principal) -> int:
    """Start a year from another year's estimates (e.g. last year's DfE
    table for this year's predictions). Existing rows are kept."""
    _require(actor, "estimate_copy")
    problems: list[str] = []
    src, dst = _academic_year(from_year, problems), _academic_year(to_year, problems)
    if not problems and src == dst:
        problems.append("Choose two different years")
    if not problems and not estimates(src):  # type: ignore[arg-type]
        problems.append(f"There are no estimates for {src}")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        n = conn.execute(
            "INSERT OR IGNORE INTO p8_estimates (academic_year, ks2_from, expected_a8, "
            "expected_english, expected_maths, expected_ebacc, expected_open, updated_by) "
            "SELECT ?, ks2_from, expected_a8, expected_english, expected_maths, expected_ebacc, "
            "expected_open, ? FROM p8_estimates WHERE academic_year = ?",
            (dst, actor.username, src)).rowcount
        _audit(conn, "estimates", "copy", actor, year=dst, source_year=src, rows=n)
    activity_log.record("headline.estimate_copy", target=dst, principal=actor, rows=n)
    return n


# ── The slot rules ───────────────────────────────────────────────────

@dataclass(frozen=True)
class Qual:
    """One qualification result to place in a slot."""
    subject: str
    category: str | None
    qualification: str
    grade: str
    points: float | None
    note: str = ""


def points_for(grade: str | None, qualification: str = "GCSE") -> float | None:
    """Points for one qualification's grade (None = not on a points scale)."""
    g = str(grade or "").strip().upper()
    if not g:
        return None
    if qualification == "BTEC":
        return BTEC_POINTS.get(g.replace("DIST*", "D*"))
    if g in GCSE_POINTS:
        return GCSE_POINTS[g]
    return None


def _quals(subject: str, category: str | None, qualification: str, grade: str | None
           ) -> list[Qual]:
    """A subject result as qualifications - two for combined science."""
    g = str(grade or "").strip().upper()
    if not g:
        return []
    q = "GCSE" if qualification in ("GCSE", "IGCSE") else qualification
    if qualification == "GCSE short course":
        return [Qual(subject, category, qualification, g, None, "short course - not counted")]
    if q not in ("GCSE", "BTEC"):
        return [Qual(subject, category, qualification, g, None, "no points scale")]
    combined = category == "Science" and "combined" in subject.lower()
    m = re.fullmatch(r"(\d)-(\d)", g)
    if m:
        pts = (int(m.group(1)) + int(m.group(2))) / 2
        return [Qual(f"{subject} ({i})", category, qualification, g, pts) for i in (1, 2)]
    pts = points_for(g, q)
    if pts is None:
        return [Qual(subject, category, qualification, g, None, f"grade {g} has no points")]
    if combined:
        return [Qual(f"{subject} ({i})", category, qualification, g, pts) for i in (1, 2)]
    return [Qual(subject, category, qualification, g, pts)]


def slot_grades(results: list[tuple[str, str | None, str, str | None]]) -> dict[str, Any]:
    """Fill the Attainment 8 slots from (subject, EBacc category,
    qualification, grade) results. Returns the slot grades, element points,
    total, whether English counted twice, EBacc entry and a per-slot
    ``detail`` (plus results not counted)."""
    quals = [q for r in results for q in _quals(*r)]
    uncounted = [q for q in quals if q.points is None]
    pool = [q for q in quals if q.points is not None]
    best = lambda qs: max(qs, key=lambda q: q.points) if qs else None  # noqa: E731
    english = [q for q in pool if q.category == "English"]
    lit = [q for q in english if "lit" in q.subject.lower()]
    lang = [q for q in english if q not in lit]
    both = bool(lit) and bool(lang)
    eng = best(english)
    maths = best([q for q in pool if q.category == "Maths"])
    used = [q for q in (eng, maths) if q is not None]
    rest = [q for q in pool if q not in used]
    rank = lambda qs: sorted(qs, key=lambda q: -q.points)  # noqa: E731
    ebacc = rank([q for q in rest if q.category in EBACC_SLOT_CATEGORIES])[:3]
    rest = [q for q in rest if q not in ebacc]
    open_ = rank(rest)[:3]
    out: dict[str, Any] = {s: None for s in SLOTS}
    detail: list[dict[str, Any]] = []

    def put(slot: str, q: Qual | None, weight: int = 1) -> float:
        out[slot] = q.grade if q else None
        pts = (q.points or 0.0) * weight if q else 0.0
        detail.append({"slot": SLOT_LABELS[slot], "subject": q.subject if q else None,
                       "grade": q.grade if q else None, "points": pts,
                       "weight": weight})
        return pts

    e_pts = put("english_grade", eng, 2 if both else 1)
    m_pts = put("maths_grade", maths, 2)
    b_pts = sum(put(f"ebacc{i + 1}_grade", ebacc[i] if i < len(ebacc) else None)
                for i in range(3))
    o_pts = sum(put(f"open{i + 1}_grade", open_[i] if i < len(open_) else None)
                for i in range(3))
    for q in uncounted:
        detail.append({"slot": "Not counted", "subject": q.subject, "grade": q.grade,
                       "points": 0.0, "weight": 0, "note": q.note})
    sciences = sum(1 for q in quals if q.category == "Science")
    out.update({
        "english_points": e_pts, "maths_points": m_pts, "ebacc_points": b_pts,
        "open_points": o_pts, "total_points": round(e_pts + m_pts + b_pts + o_pts, 2),
        "english_double": both, "detail": detail,
        # EBacc entry: English language and literature, maths, two sciences
        # (combined counts as two), a language and a humanity.
        "ebacc_entered": both and maths is not None and sciences >= 2
        and any(q.category == "Languages" for q in quals)
        and any(q.category == "Humanities" for q in quals)})
    return out


def manual_points(grades: dict[str, str | None], english_double: bool = True
                  ) -> dict[str, Any]:
    """Points for grades typed into the slots (old New / update dialog)."""
    problems: list[str] = []
    out: dict[str, Any] = {}
    for slot in SLOTS:
        g = str(grades.get(slot) or "").strip().upper() or None
        if g is not None and g not in GCSE_POINTS and not re.fullmatch(r"\d-\d", g) \
                and g not in BTEC_POINTS:
            problems.append(f"{SLOT_LABELS[slot]}: grade must be 9-1, U, a combined grade "
                            "like 6-5 or a BTEC grade (D*, D, M, P)")
        out[slot] = g

    def pts(g: str | None) -> float:
        if not g:
            return 0.0
        m = re.fullmatch(r"(\d)-(\d)", g)
        if m:
            return (int(m.group(1)) + int(m.group(2))) / 2
        return GCSE_POINTS.get(g, BTEC_POINTS.get(g, 0.0))
    if problems:
        raise ValidationError(problems)
    e = pts(out["english_grade"]) * (2 if english_double else 1)
    m = pts(out["maths_grade"]) * 2
    b = sum(pts(out[f"ebacc{i}_grade"]) for i in (1, 2, 3))
    o = sum(pts(out[f"open{i}_grade"]) for i in (1, 2, 3))
    detail = [{"slot": SLOT_LABELS[s], "subject": None, "grade": out[s],
               "points": pts(out[s]) * (2 if s == "maths_grade" or (
                   s == "english_grade" and english_double) else 1),
               "weight": 2 if s == "maths_grade" or (s == "english_grade" and english_double)
               else 1} for s in SLOTS]
    out.update({"english_points": e, "maths_points": m, "ebacc_points": b, "open_points": o,
                "total_points": round(e + m + b + o, 2), "english_double": english_double,
                "ebacc_entered": None, "detail": detail})
    return out


# ── Where the grades come from ───────────────────────────────────────

def _subject_info() -> dict[int, S.Subject]:
    return {s.subject_id: s for s in S.list_subjects(active_only=False)}


def _year_end(academic_year: str) -> int:
    return int(academic_year[:4]) + 1


def _actual(pupils: list[P.Pupil], academic_year: str) -> tuple[dict, str]:
    """Released exam results (GCSE record, which hides embargoed grades),
    the newest per subject up to that summer."""
    from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
    subs = _subject_info()
    out: dict[int, list] = {}
    for p in pupils:
        latest: dict[int, Any] = {}
        for r in sorted(G.for_pupil(p.pupil_id), key=lambda r: r.exam_year):
            if r.exam_year <= _year_end(academic_year):
                latest[r.subject_id] = r
        out[p.pupil_id] = [(r.subject_name or subs[r.subject_id].name,
                            r.ebacc_category or subs[r.subject_id].ebacc_category,
                            r.qualification, r.grade) for r in latest.values()]
    return out, f"Exam results up to summer {_year_end(academic_year)}"


def _predicted(pupils: list[P.Pupil], year_group: int, point_id: int | None
               ) -> tuple[dict, str]:
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    if point_id is None:
        pts = [pt for pt in AP.list_points(status="Published") if year_group in pt.years]
        if not pts:
            raise ValidationError([f"No published assessment point covers Year {year_group} - "
                                   "publish one, or choose a point"])
        pt = pts[0]
    else:
        pt = AP.get_point(int(point_id))
    subs = _subject_info()
    ids = {p.pupil_id for p in pupils}
    out: dict[int, list] = {pid: [] for pid in ids}
    for g in AP.grades(pt.point_id, year_group=year_group):
        if g.pupil_id in ids:
            s = subs.get(g.subject_id)
            grade = (g.predicted or g.working_at) if pt.collect_predicted else g.working_at
            if s is not None and grade:
                out[g.pupil_id].append((s.name, s.ebacc_category, s.qualification, grade))
    what = "predicted grades" if pt.collect_predicted else "working-at grades"
    return out, f"{pt.name} ({pt.academic_year}) {what}"


def _estimated(pupils: list[P.Pupil]) -> tuple[dict, str]:
    from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
    subs = _subject_info()
    ids = {p.pupil_id for p in pupils}
    out: dict[int, list] = {pid: [] for pid in ids}
    series: set[str] = set()
    for (pid, sid), (grade, name, _end) in MX.latest_grades().items():
        s = subs.get(sid)
        if pid in ids and s is not None:
            out[pid].append((s.name, s.ebacc_category, s.qualification, grade))
            series.add(name)
    if not series:
        raise ValidationError(["No completed mock exam series has grades for these pupils"])
    return out, "Mock exams: " + ", ".join(sorted(series))


def _targets(pupils: list[P.Pupil], year_group: int) -> tuple[dict, str]:
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    subs = _subject_info()
    ids = {p.pupil_id for p in pupils}
    out: dict[int, list] = {pid: [] for pid in ids}
    for t in TGR.list_targets(year_group=year_group):
        s = subs.get(t.subject_id)
        if t.pupil_id in ids and s is not None:
            out[t.pupil_id].append((s.name, s.ebacc_category, s.qualification, t.target_grade))
    return out, "Target grades"


# ── Attainment 8 records ─────────────────────────────────────────────

_A8_SELECT = "SELECT r.*" + _PCOLS + " FROM attainment8_records r" + _JOIN


def get(record_id: int) -> A8Record:
    with database.connect() as conn:
        r = conn.execute(_A8_SELECT + " WHERE r.record_id = ?", (int(record_id),)).fetchone()
    if r is None:
        raise NotFound(f"No Attainment 8 record {record_id}")
    return _a8(r)


def get_for(pupil_id: int, academic_year: str, record_source: str) -> A8Record | None:
    with database.connect() as conn:
        r = conn.execute(_A8_SELECT + " WHERE r.pupil_id = ? AND r.academic_year = ? AND "
                         "r.record_source = ?", (int(pupil_id), academic_year,
                                                 record_source)).fetchone()
    return _a8(r) if r else None


def list_records(*, year_group: int | str | None = None, academic_year: str | None = None,
                 record_source: str | None = None, pupil_id: int | None = None
                 ) -> list[A8Record]:
    sql, where, params = _A8_SELECT, [], []
    if record_source not in (None, "") and record_source not in SOURCES:
        raise ValidationError([f"Source filter must be one of {', '.join(SOURCES)}"])
    for col, val in (("p.year_group", year_group), ("r.academic_year", academic_year),
                     ("r.record_source", record_source), ("r.pupil_id", pupil_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val) if col in ("p.year_group", "r.pupil_id") else val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_a8(r) for r in conn.execute(
            sql + " ORDER BY r.academic_year DESC, p.legal_last_name COLLATE NOCASE, "
                  "p.legal_first_name COLLATE NOCASE, r.record_source", params)]


def _save_a8(conn, pupil_id: int, year: str, source: str, s: dict[str, Any], method: str,
             based_on: str | None, notes: str | None, actor: Principal) -> None:
    conn.execute(
        "INSERT INTO attainment8_records (pupil_id, academic_year, record_source, "
        + ", ".join(SLOTS) + ", english_points, maths_points, ebacc_points, open_points, "
        "total_points, english_double, ebacc_entered, slot_detail, method, based_on, notes, "
        "recorded_by) VALUES (" + ", ".join("?" * (3 + len(SLOTS) + 12)) + ") "
        "ON CONFLICT (pupil_id, academic_year, record_source) DO UPDATE SET "
        + ", ".join(f"{c} = excluded.{c}" for c in (*SLOTS, "english_points", "maths_points",
                                                     "ebacc_points", "open_points",
                                                     "total_points", "english_double",
                                                     "ebacc_entered", "slot_detail", "method",
                                                     "based_on", "notes", "recorded_by"))
        + ", updated_at = datetime('now')",
        (pupil_id, year, source, *(s[k] for k in SLOTS), s["english_points"],
         s["maths_points"], s["ebacc_points"], s["open_points"], s["total_points"],
         int(s["english_double"]), None if s["ebacc_entered"] is None else
         int(s["ebacc_entered"]), json.dumps(s["detail"]), method, based_on, notes,
         actor.username))


def upsert(data: dict[str, Any], *, actor: Principal) -> A8Record:
    """Enter (or replace) a record by hand from the slot grades (the old
    New / update)."""
    p = _pupil(data.get("pupil_id") or data.get("pupil") or "")
    _require(actor, "a8_upsert", p.admission_no)
    problems: list[str] = []
    year = _academic_year(data.get("academic_year") or current_year(), problems)
    source = str(data.get("record_source") or DEFAULT_SOURCE).strip().title()
    if source not in SOURCES:
        problems.append(f"Record source must be one of {', '.join(SOURCES)}")
    try:
        s = manual_points({k: data.get(k) for k in SLOTS},
                          bool(data.get("english_double", True)))
    except ValidationError as e:
        problems.extend(e.problems)
        s = {}
    if problems:
        activity_log.record("headline.a8_upsert", target=p.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        _save_a8(conn, p.pupil_id, year, source, s, "Entered", None,  # type: ignore[arg-type]
                 _text(data.get("notes")), actor)
        _audit(conn, "a8", "entered", actor, p.pupil_id, year=year, source=source)
    activity_log.record("headline.a8_upsert", target=p.admission_no, principal=actor,
                        source=source)
    return get_for(p.pupil_id, year, source)  # type: ignore[arg-type,return-value]


def update(record_id: int, changes: dict[str, Any], *, actor: Principal) -> A8Record:
    """Edit a record's slot grades or notes; it becomes an entered record
    (a recalculation won't overwrite it)."""
    rec = get(record_id)
    merged = {"pupil_id": rec.pupil_id, "academic_year": rec.academic_year,
              "record_source": rec.record_source, "english_double": rec.english_double,
              "notes": rec.notes, **{s: rec.grade(s) for s in SLOTS}, **changes}
    if (merged["academic_year"], merged["record_source"]) != (rec.academic_year,
                                                               rec.record_source):
        raise ValidationError(["The year and source of a record can't change - make a new "
                               "record"])
    return upsert(merged, actor=actor)


def delete(record_id: int, *, actor: Principal) -> bool:
    rec = get(record_id)
    _require(actor, "a8_delete", rec.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM attainment8_records WHERE record_id = ?", (rec.record_id,))
        _audit(conn, "a8", "delete", actor, rec.pupil_id, year=rec.academic_year,
               source=rec.record_source)
    activity_log.record("headline.a8_delete", target=rec.admission_no, principal=actor)
    return True


def calculate(year_group: int, record_source: str, *, actor: Principal,
              academic_year: str | None = None, point_id: int | None = None,
              overwrite_entered: bool = False) -> dict[str, Any]:
    """Work out every on-roll pupil's A8 in *year_group* from *record_source*
    data. Returns {'saved', 'kept' (entered by hand, left alone), 'no_data',
    'based_on'}."""
    _require(actor, "a8_calculate", f"Y{year_group}")
    problems: list[str] = []
    year = _academic_year(academic_year or current_year(), problems)
    if record_source not in SOURCES:
        problems.append(f"Source must be one of {', '.join(SOURCES)}")
    if int(year_group) not in P.YEAR_GROUPS:
        problems.append("Choose a year group")
    if problems:
        raise ValidationError(problems)
    pupils = P.list_pupils(year_group=int(year_group))
    if not pupils:
        raise ValidationError([f"There are no pupils on roll in Year {year_group}"])
    if record_source == "Actual":
        data, based_on = _actual(pupils, year)  # type: ignore[arg-type]
    elif record_source == "Predicted":
        data, based_on = _predicted(pupils, int(year_group), point_id)
    elif record_source == "Estimated":
        data, based_on = _estimated(pupils)
    else:
        data, based_on = _targets(pupils, int(year_group))
    saved, kept, none = [], [], []
    with database.connect() as conn:
        entered = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM attainment8_records WHERE academic_year = ? AND "
            "record_source = ? AND method = 'Entered'", (year, record_source))}
        for p in pupils:
            results = data.get(p.pupil_id) or []
            if not results:
                none.append(p.admission_no)
                continue
            if p.pupil_id in entered and not overwrite_entered:
                kept.append(p.admission_no)
                continue
            _save_a8(conn, p.pupil_id, year, record_source,  # type: ignore[arg-type]
                     slot_grades(results), "Calculated", based_on, None, actor)
            saved.append(p.admission_no)
        _audit(conn, "a8", "calculate", actor, year=year, source=record_source,
               year_group=int(year_group), saved=len(saved), kept=len(kept),
               no_data=len(none), based_on=based_on)
    activity_log.record("headline.a8_calculate", target=f"Y{year_group}", principal=actor,
                        source=record_source, saved=len(saved), kept=len(kept),
                        no_data=len(none))
    return {"saved": saved, "kept": kept, "no_data": none, "based_on": based_on,
            "academic_year": year}


def cohort_summary(*, year_group: int | str | None = None, academic_year: str | None = None,
                   record_source: str | None = None) -> dict[str, Any]:
    """The old Summary: records, average A8 (and average grade), spread."""
    rows = list_records(year_group=year_group, academic_year=academic_year,
                        record_source=record_source)
    if not rows:
        return {"records": 0, "average_a8": None, "average_grade": None, "highest": None,
                "lowest": None, "by_source": {}, "bands": {}}
    totals = [r.total_points for r in rows]
    bands = Counter(_band(t) for t in totals)
    return {"records": len(rows), "average_a8": round(sum(totals) / len(totals), 2),
            "average_grade": round(sum(totals) / len(totals) / 10, 2),
            "highest": max(totals), "lowest": min(totals),
            "by_source": dict(Counter(r.record_source for r in rows)),
            "bands": {b: bands.get(b, 0) for b in _BANDS}}


_BANDS = ("70+", "60-69", "50-59", "40-49", "30-39", "under 30")


def _band(total: float) -> str:
    for low, label in ((70, "70+"), (60, "60-69"), (50, "50-59"), (40, "40-49"),
                       (30, "30-39")):
        if total >= low:
            return label
    return "under 30"


# ── Progress 8 records ───────────────────────────────────────────────

_P8_SELECT = "SELECT r.*" + _PCOLS + " FROM progress8_records r" + _JOIN


def get_p8(record_id: int) -> P8Record:
    with database.connect() as conn:
        r = conn.execute(_P8_SELECT + " WHERE r.record_id = ?", (int(record_id),)).fetchone()
    if r is None:
        raise NotFound(f"No Progress 8 record {record_id}")
    return _p8(r)


def get_p8_for(pupil_id: int, academic_year: str) -> P8Record | None:
    with database.connect() as conn:
        r = conn.execute(_P8_SELECT + " WHERE r.pupil_id = ? AND r.academic_year = ?",
                         (int(pupil_id), academic_year)).fetchone()
    return _p8(r) if r else None


def list_p8(*, year_group: int | str | None = None, academic_year: str | None = None,
            pupil_id: int | None = None) -> list[P8Record]:
    sql, where, params = _P8_SELECT, [], []
    for col, val in (("p.year_group", year_group), ("r.academic_year", academic_year),
                     ("r.pupil_id", pupil_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val) if col != "r.academic_year" else val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_p8(r) for r in conn.execute(
            sql + " ORDER BY r.academic_year DESC, p.legal_last_name COLLATE NOCASE, "
                  "p.legal_first_name COLLATE NOCASE", params)]


def _best_a8(pupil_id: int, academic_year: str, prefer: str | None = None
             ) -> A8Record | None:
    order = ((prefer,) if prefer else ()) + tuple(s for s in A8_PREFERENCE if s != prefer)
    for src in order:
        rec = get_for(pupil_id, academic_year, src)
        if rec is not None:
            return rec
    return None


def _p8_values(a8: A8Record | None, expected: float, est: Estimate | None
               ) -> dict[str, float | None]:
    out: dict[str, float | None] = {"attainment_8": a8.total_points if a8 else None,
                                    "progress_8": None}
    for el in ELEMENTS:
        out[f"p8_{el}"] = None
    if a8 is None:
        return out
    out["progress_8"] = round((a8.total_points - expected) / 10, 2)
    if est is not None:
        for el in ELEMENTS:
            e = getattr(est, f"expected_{el}")
            if e is not None:
                out[f"p8_{el}"] = round((getattr(a8, f"{el}_points") - e)
                                        / ELEMENT_SLOTS[el], 2)
    return out


def _save_p8(conn, pupil_id: int, year: str, ks2: float, expected: float, expected_from: str,
             a8: A8Record | None, values: dict[str, Any], method: str, notes: str | None,
             actor: Principal, a8_value: float | None = None) -> None:
    att = values["attainment_8"] if a8_value is None else a8_value
    conn.execute(
        "INSERT INTO progress8_records (pupil_id, academic_year, ks2_prior, expected_a8, "
        "expected_from, attainment_8, a8_source, progress_8, p8_english, p8_maths, p8_ebacc, "
        "p8_open, method, notes, recorded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?) ON CONFLICT (pupil_id, academic_year) DO UPDATE SET ks2_prior = "
        "excluded.ks2_prior, expected_a8 = excluded.expected_a8, expected_from = "
        "excluded.expected_from, attainment_8 = excluded.attainment_8, a8_source = "
        "excluded.a8_source, progress_8 = excluded.progress_8, p8_english = "
        "excluded.p8_english, p8_maths = excluded.p8_maths, p8_ebacc = excluded.p8_ebacc, "
        "p8_open = excluded.p8_open, method = excluded.method, notes = excluded.notes, "
        "recorded_by = excluded.recorded_by, updated_at = datetime('now')",
        (pupil_id, year, ks2, expected, expected_from, att,
         a8.record_source if a8 else ("Entered" if a8_value is not None else None),
         values["progress_8"] if a8_value is None else
         round((a8_value - expected) / 10, 2),
         values["p8_english"], values["p8_maths"], values["p8_ebacc"], values["p8_open"],
         method, notes, actor.username))


def upsert_p8(data: dict[str, Any], *, actor: Principal) -> P8Record:
    """Set a pupil's Progress 8 record (the old New / update). KS2 and the
    expected A8 default to the pupil's KS2 record and the year's estimates;
    the A8 to their best A8 record (Actual first) unless one is given."""
    p = _pupil(data.get("pupil_id") or data.get("pupil") or "")
    _require(actor, "p8_upsert", p.admission_no)
    problems: list[str] = []
    year = _academic_year(data.get("academic_year") or current_year(), problems)
    ks2 = _number(data.get("ks2_prior"), "KS2 prior attainment", problems, low=KS2_MIN,
                  high=KS2_MAX)
    if ks2 is None and not problems:
        k = get_ks2(p.pupil_id)
        ks2 = k.prior if k else None
        if ks2 is None:
            problems.append("Give the KS2 prior attainment (average scaled score, 80-120), "
                            "or enter the pupil's KS2 results first")
    expected = _number(data.get("expected_a8"), "Expected A8", problems, low=0, high=90)
    est = None
    expected_from = "Entered"
    if expected is None and ks2 is not None and year:
        est = estimate_for(year, ks2)
        if est is None:
            problems.append(f"There are no Progress 8 estimates for {year} - enter them, or "
                            "give the expected A8")
        else:
            expected, expected_from = est.expected_a8, f"Estimates {year}"
    a8_given = _number(data.get("attainment_8"), "Attainment 8", problems, low=0, high=90)
    if problems:
        activity_log.record("headline.p8_upsert", target=p.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    a8 = None if a8_given is not None else _best_a8(p.pupil_id, year,  # type: ignore[arg-type]
                                                    data.get("a8_source"))
    values = _p8_values(a8, expected, est)  # type: ignore[arg-type]
    with database.connect() as conn:
        _save_p8(conn, p.pupil_id, year, ks2, expected, expected_from,  # type: ignore[arg-type]
                 a8, values, "Entered", _text(data.get("notes")), actor, a8_given)
        _audit(conn, "p8", "entered", actor, p.pupil_id, year=year)
    activity_log.record("headline.p8_upsert", target=p.admission_no, principal=actor)
    return get_p8_for(p.pupil_id, year)  # type: ignore[arg-type,return-value]


def update_p8(record_id: int, changes: dict[str, Any], *, actor: Principal) -> P8Record:
    rec = get_p8(record_id)
    merged = {"pupil_id": rec.pupil_id, "academic_year": rec.academic_year,
              "ks2_prior": rec.ks2_prior, "notes": rec.notes,
              "expected_a8": rec.expected_a8 if rec.expected_from == "Entered" else None,
              "attainment_8": rec.attainment_8 if rec.a8_source == "Entered" else None,
              **changes}
    if merged["academic_year"] != rec.academic_year:
        raise ValidationError(["The year of a record can't change - make a new record"])
    return upsert_p8(merged, actor=actor)


def refresh_a8(record_id: int, *, actor: Principal, prefer: str | None = None) -> P8Record:
    """Re-pull the A8 from the A8 records (the old Refresh A8)."""
    rec = get_p8(record_id)
    _require(actor, "p8_refresh", rec.admission_no)
    a8 = _best_a8(rec.pupil_id, rec.academic_year, prefer)
    if a8 is None:
        raise ValidationError([f"{rec.pupil_name} has no Attainment 8 record for "
                               f"{rec.academic_year}"])
    est = (estimate_for(rec.academic_year, rec.ks2_prior)
           if rec.expected_from != "Entered" else None)
    values = _p8_values(a8, rec.expected_a8, est)
    with database.connect() as conn:
        _save_p8(conn, rec.pupil_id, rec.academic_year, rec.ks2_prior, rec.expected_a8,
                 rec.expected_from, a8, values, rec.method, rec.notes, actor)
        _audit(conn, "p8", "refresh_a8", actor, rec.pupil_id, year=rec.academic_year,
               source=a8.record_source)
    activity_log.record("headline.p8_refresh", target=rec.admission_no, principal=actor)
    return get_p8(record_id)


def delete_p8(record_id: int, *, actor: Principal) -> bool:
    rec = get_p8(record_id)
    _require(actor, "p8_delete", rec.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM progress8_records WHERE record_id = ?", (rec.record_id,))
        _audit(conn, "p8", "delete", actor, rec.pupil_id, year=rec.academic_year)
    activity_log.record("headline.p8_delete", target=rec.admission_no, principal=actor)
    return True


def calculate_p8(year_group: int, *, actor: Principal, academic_year: str | None = None,
                 prefer: str | None = None, overwrite_entered: bool = False
                 ) -> dict[str, Any]:
    """Progress 8 for every on-roll pupil in *year_group* with KS2 data and
    an A8 record (best source, or *prefer*), from the year's estimates."""
    _require(actor, "p8_calculate", f"Y{year_group}")
    problems: list[str] = []
    year = _academic_year(academic_year or current_year(), problems)
    if prefer not in (None, "") and prefer not in SOURCES:
        problems.append(f"Source must be one of {', '.join(SOURCES)}")
    table = estimates(year) if year else []
    if year and not table:
        problems.append(f"There are no Progress 8 estimates for {year} - enter the DfE "
                        "estimates (or copy last year's) first")
    if problems:
        raise ValidationError(problems)
    have = ks2_map()
    saved, no_ks2, no_a8, kept = [], [], [], []
    with database.connect() as conn:
        entered = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM progress8_records WHERE academic_year = ? AND "
            "method = 'Entered'", (year,))}
    rows = []
    for p in P.list_pupils(year_group=int(year_group)):
        k = have.get(p.pupil_id)
        if k is None or k.prior is None:
            no_ks2.append(p.admission_no)
            continue
        a8 = _best_a8(p.pupil_id, year, prefer or None)  # type: ignore[arg-type]
        if a8 is None:
            no_a8.append(p.admission_no)
            continue
        if p.pupil_id in entered and not overwrite_entered:
            kept.append(p.admission_no)
            continue
        est = estimate_for(year, k.prior, table)  # type: ignore[arg-type]
        rows.append((p, k, a8, est))
    with database.connect() as conn:
        for p, k, a8, est in rows:
            _save_p8(conn, p.pupil_id, year, k.prior, est.expected_a8,  # type: ignore[arg-type]
                     f"Estimates {year}", a8, _p8_values(a8, est.expected_a8, est),
                     "Calculated", None, actor)
            saved.append(p.admission_no)
        _audit(conn, "p8", "calculate", actor, year=year, year_group=int(year_group),
               saved=len(saved), no_ks2=len(no_ks2), no_a8=len(no_a8), kept=len(kept))
    activity_log.record("headline.p8_calculate", target=f"Y{year_group}", principal=actor,
                        saved=len(saved), no_ks2=len(no_ks2), no_a8=len(no_a8),
                        kept=len(kept))
    return {"saved": saved, "no_ks2": no_ks2, "no_a8": no_a8, "kept": kept,
            "academic_year": year}


def p8_summary(*, year_group: int | str | None = None, academic_year: str | None = None
               ) -> dict[str, Any]:
    """The old Progress 8 Summary: records, average P8, spread."""
    rows = [r for r in list_p8(year_group=year_group, academic_year=academic_year)
            if r.progress_8 is not None]
    if not rows:
        return {"records": 0, "average_p8": None, "above_zero": 0, "below_minus_half": 0,
                "highest": None, "lowest": None}
    vals = [r.progress_8 for r in rows]
    return {"records": len(rows), "average_p8": round(sum(vals) / len(vals), 2),  # type: ignore[arg-type]
            "above_zero": sum(1 for v in vals if v > 0),  # type: ignore[operator]
            "below_minus_half": sum(1 for v in vals if v < -0.5),  # type: ignore[operator]
            "highest": max(vals), "lowest": min(vals)}  # type: ignore[type-var]


# ── Headline measures ────────────────────────────────────────────────

GROUPS: tuple[tuple[str, str], ...] = (
    ("All pupils", "all"), ("Disadvantaged (FSM)", "fsm"), ("Not disadvantaged", "not_fsm"),
    ("SEN support (K)", "sen_k"), ("EHC plan (E)", "sen_e"), ("No SEN", "sen_n"),
    ("Female", "female"), ("Male", "male"), ("EAL", "eal"), ("Not EAL", "not_eal"))


def _in(group: str, p: P.Pupil) -> bool:
    return {"all": True, "fsm": p.fsm_eligible, "not_fsm": not p.fsm_eligible,
            "sen_k": p.sen_status == "K", "sen_e": p.sen_status == "E",
            "sen_n": p.sen_status == "N", "female": p.gender == "Female",
            "male": p.gender == "Male", "eal": p.eal, "not_eal": not p.eal}[group]


def _grade_num(g: str | None) -> float | None:
    if not g:
        return None
    m = re.fullmatch(r"(\d)-(\d)", g)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2
    return GCSE_POINTS.get(g.upper())


def headline(*, year_group: int = 11, academic_year: str | None = None,
             record_source: str = "Actual") -> dict[str, Any]:
    """The headline measures for a year group from one source's A8 records
    (and this year's P8 records whose A8 came from that source)."""
    year = academic_year or current_year()
    a8s = {r.pupil_id: r for r in list_records(year_group=year_group, academic_year=year,
                                               record_source=record_source)}
    p8s = {r.pupil_id: r for r in list_p8(year_group=year_group, academic_year=year)
           if r.progress_8 is not None and r.a8_source == record_source}
    cohort = P.list_pupils(year_group=int(year_group))
    have = ks2_map()
    groups = []
    for label, key in GROUPS:
        ps = [p for p in cohort if _in(key, p)]
        rec = [a8s[p.pupil_id] for p in ps if p.pupil_id in a8s]
        prog = [p8s[p.pupil_id].progress_8 for p in ps if p.pupil_id in p8s]

        def pct(test) -> float | None:
            return round(100 * sum(1 for r in rec if test(r)) / len(rec), 1) if rec else None

        def both(n: int):
            return lambda r: (_grade_num(r.english_grade) or 0) >= n and \
                (_grade_num(r.maths_grade) or 0) >= n
        eb = [r for r in rec if r.ebacc_entered is not None]
        groups.append({
            "group": label, "key": key, "pupils": len(ps), "with_a8": len(rec),
            "average_a8": round(sum(r.total_points for r in rec) / len(rec), 1) if rec else None,
            "average_p8": round(sum(prog) / len(prog), 2) if prog else None,  # type: ignore[arg-type]
            "with_p8": len(prog),
            "eng_maths_4": pct(both(4)), "eng_maths_5": pct(both(5)),
            "ebacc_entry": (round(100 * sum(1 for r in eb if r.ebacc_entered) / len(eb), 1)
                            if eb else None)})
    by = {g["key"]: g for g in groups}

    def gap(field: str) -> float | None:
        a, b = by["fsm"][field], by["not_fsm"][field]
        return None if a is None or b is None else round(a - b, 2)
    return {"academic_year": year, "year_group": int(year_group), "source": record_source,
            "groups": groups,
            "disadvantaged_gap": {f: gap(f) for f in ("average_a8", "average_p8",
                                                       "eng_maths_4", "eng_maths_5",
                                                       "ebacc_entry")},
            "missing_a8": [p for p in cohort if p.pupil_id not in a8s],
            "missing_ks2": [p for p in cohort if (k := have.get(p.pupil_id)) is None
                            or k.prior is None]}


def for_pupil(pupil_id: int) -> dict[str, Any]:
    """A pupil's newest A8 (each source) and P8, for the profile."""
    recs = list_records(pupil_id=pupil_id)
    year = recs[0].academic_year if recs else None
    return {"academic_year": year,
            "a8": {r.record_source: r for r in recs if r.academic_year == year},
            "p8": get_p8_for(pupil_id, year) if year else None,
            "ks2": get_ks2(pupil_id)}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """A8 records with the matching P8 (one row per A8 record)."""
    rows = list_records(**filters)
    p8 = {(r.pupil_id, r.academic_year): r for r in list_p8(
        year_group=filters.get("year_group"), academic_year=filters.get("academic_year"))}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year_group", "academic_year", "source", "method",
                    *SLOTS, "english_points", "maths_points", "ebacc_points", "open_points",
                    "attainment_8", "average_grade", "ebacc_entered", "ks2_prior",
                    "expected_a8", "progress_8", "based_on"])
        for r in rows:
            q = p8.get((r.pupil_id, r.academic_year))
            q = q if q and q.a8_source == r.record_source else None
            w.writerow([_safe(r.admission_no), _safe(r.pupil_name), r.year_group,
                        r.academic_year, r.record_source, r.method,
                        *(_safe(r.grade(s)) for s in SLOTS), r.english_points, r.maths_points,
                        r.ebacc_points, r.open_points, r.total_points, r.average_grade,
                        "" if r.ebacc_entered is None else ("yes" if r.ebacc_entered else "no"),
                        q.ks2_prior if q else "", q.expected_a8 if q else "",
                        q.progress_8 if q and q.progress_8 is not None else "",
                        _safe(r.based_on)])
    activity_log.record("headline.export", principal=actor, rows=len(rows))
    return len(rows)
