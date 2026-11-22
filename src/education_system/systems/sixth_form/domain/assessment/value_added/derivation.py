"""Expected grades and value added, derived from prior attainment.

Value-added records used to carry an ``expected_grade`` somebody typed
in. This module works it out instead:

1. **Prior attainment** — the learner's average GCSE point score, from
   QUAL's ``prior_attainment.average_gcse_score``.
2. **Benchmark table** (``va_benchmark_bands``) — for a qualification
   type (and optionally one subject) a set of average-GCSE bands, each
   giving an *expected grade* and a *minimum expected grade* (MEG).
   Subject-specific bands win over the all-subjects bands for their type.
3. **Actual grade** — the learner's released exam result in that
   subject (latest series; best grade within a series).
4. **VA score** = actual points − expected points, both on the
   qualification's own grade scale (``grade_scales.grade_points`` — an
   ordinal, one point per grade). Cohort VA is the mean of the student
   VA scores; subject VA the mean within a subject.

**The band table starts empty.** "Restore placeholder bands" loads an
optional starter set, which is not ALPS or DfE data: a straight line —
one A-level grade per GCSE point (APS 6 → B, 7 → A …). It is flagged ``is_placeholder``,
labelled as such everywhere it is shown, and every result computed from
it says so. Replace it with your ALPS / DfE L3VA benchmark bands (per
subject where you have them) before using any figure for judgement.
"""

from __future__ import annotations

import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_VALUE_ADDED_DB

PLACEHOLDER_SOURCE = (
    "PLACEHOLDER - linear (one grade per GCSE point); NOT ALPS/DfE data. "
    "Replace with your ALPS / L3VA benchmarks.")

# Linear placeholder: (min APS, max APS or None, grade). One A-level grade
# per average-GCSE point, centred on whole points.
_PLACEHOLDER_BANDS: dict[str, tuple[tuple[float, float | None, str], ...]] = {
    "A Level": ((0.0, 3.5, "E"), (3.5, 4.5, "D"), (4.5, 5.5, "C"),
                (5.5, 6.5, "B"), (6.5, 7.5, "A"), (7.5, None, "A*")),
    "AS Level": ((0.0, 3.5, "E"), (3.5, 4.5, "D"), (4.5, 5.5, "C"),
                 (5.5, 6.5, "B"), (6.5, None, "A")),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS va_benchmark_bands (
    band_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    qualification_type TEXT NOT NULL,
    subject            TEXT,
    min_aps            REAL NOT NULL,
    max_aps            REAL,
    expected_grade     TEXT NOT NULL,
    meg_grade          TEXT,
    source             TEXT NOT NULL,
    is_placeholder     INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_vab_type ON va_benchmark_bands(qualification_type);

CREATE TABLE IF NOT EXISTS va_benchmark_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
"""


class ValidationError(ValueError):
    """Invalid benchmark input."""


@dataclass
class Band:
    band_id: int
    qualification_type: str
    subject: str | None
    min_aps: float
    max_aps: float | None
    expected_grade: str
    meg_grade: str | None
    source: str
    is_placeholder: bool
    notes: str | None

    @property
    def minimum_grade(self) -> str:
        """MEG falls back to the expected grade when not set."""
        return self.meg_grade or self.expected_grade

    @property
    def range_label(self) -> str:
        top = f"{self.max_aps:.2f}" if self.max_aps is not None else "+"
        return f"{self.min_aps:.2f} – {top}"


@dataclass
class ActualResult:
    subject: str
    grade: str
    year: int
    season: str
    qualification_type: str | None


@dataclass
class DerivedVA:
    student_id: str
    student_name: str
    subject: str
    qualification_type: str
    aim_status: str
    aps: float | None
    expected_grade: str | None
    meg_grade: str | None
    actual_grade: str | None
    result_year: int | None
    expected_points: int | None
    actual_points: int | None
    placeholder: bool
    note: str = ""

    @property
    def va(self) -> float | None:
        if self.expected_points is None or self.actual_points is None:
            return None
        return float(self.actual_points - self.expected_points)


@dataclass
class SubjectVA:
    subject: str
    learners: int
    with_results: int
    mean_va: float | None


@dataclass
class CohortVA:
    rows: list[DerivedVA] = field(default_factory=list)
    by_subject: list[SubjectVA] = field(default_factory=list)
    mean_va: float | None = None
    with_results: int = 0
    placeholder_in_use: bool = False


# ── DB ─────────────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY: set[str] = set()


def init_db() -> None:
    """Create the benchmark tables (no bands are seeded)."""
    key = str(DB_PATH)
    if key in _READY:
        return
    with _connect() as conn:
        # Starts empty: placeholder bands are only loaded when a user
        # chooses "Restore placeholder bands" (restore_placeholder).
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


def _seed(conn: db.Connection) -> int:
    n = 0
    for qtype, bands in _PLACEHOLDER_BANDS.items():
        for lo, hi, grade in bands:
            conn.execute(
                "INSERT INTO va_benchmark_bands (qualification_type, subject,"
                " min_aps, max_aps, expected_grade, meg_grade, source,"
                " is_placeholder, notes) VALUES (?, NULL, ?, ?, ?, ?, ?, 1, ?)",
                (qtype, lo, hi, grade, grade, PLACEHOLDER_SOURCE,
                 "Seeded placeholder - edit or delete and enter your "
                 "benchmark bands."))
            n += 1
    return n


def restore_placeholder() -> int:
    """Delete every placeholder band and re-seed it (real bands untouched)."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM va_benchmark_bands WHERE is_placeholder = 1")
        n = _seed(conn)
        conn.commit()
    return n


def _row(r: db.Row) -> Band:
    return Band(band_id=r["band_id"],
                qualification_type=r["qualification_type"],
                subject=r["subject"], min_aps=float(r["min_aps"]),
                max_aps=(None if r["max_aps"] is None else float(r["max_aps"])),
                expected_grade=r["expected_grade"], meg_grade=r["meg_grade"],
                source=r["source"], is_placeholder=bool(r["is_placeholder"]),
                notes=r["notes"])


# ── Bands CRUD ─────────────────────────────────────────────────────

def list_bands(*, qualification_type: str | None = None,
               subject: str | None = None) -> list[Band]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if qualification_type:
        clauses.append("qualification_type = ?")
        args.append(qualification_type)
    if subject is not None:
        clauses.append("COALESCE(subject, '') = ?")
        args.append(subject)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"SELECT * FROM va_benchmark_bands {where} "
            "ORDER BY qualification_type, COALESCE(subject, ''), min_aps",
            args)]


def get_band(band_id: int) -> Band | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM va_benchmark_bands WHERE band_id = ?",
                         (int(band_id),)).fetchone()
    return _row(r) if r else None


def placeholder_in_use() -> bool:
    init_db()
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM va_benchmark_bands "
                            "WHERE is_placeholder = 1 LIMIT 1").fetchone() is not None


def _num(value: Any, label: str, *, required: bool) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if not 0 <= v <= 9:
        raise ValidationError(f"{label} must be between 0 and 9")
    return v


def _validate(data: dict[str, Any], *, existing_id: int | None = None
              ) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    qtype = grade_scales.canonical_type(str(data.get("qualification_type") or ""))
    if qtype is None:
        raise ValidationError("Qualification type must be one of: "
                              + ", ".join(grade_scales.QUALIFICATION_TYPES))
    subject = (str(data.get("subject") or "").strip()) or None
    lo = _num(data.get("min_aps"), "Minimum average GCSE", required=True)
    hi = _num(data.get("max_aps"), "Maximum average GCSE", required=False)
    if hi is not None and hi <= lo:
        raise ValidationError("Maximum must be above the minimum")
    try:
        exp = grade_scales.validate_grade(str(data.get("expected_grade") or ""),
                                          qtype)
        meg_raw = str(data.get("meg_grade") or "").strip()
        meg = grade_scales.validate_grade(meg_raw, qtype) if meg_raw else None
    except ValueError as e:
        raise ValidationError(str(e)) from None
    source = (str(data.get("source") or "").strip()
              or "Entered by hand")
    # Bands for the same (type, subject) must not overlap.
    for b in list_bands(qualification_type=qtype, subject=subject or ""):
        if b.band_id == existing_id:
            continue
        b_hi = b.max_aps if b.max_aps is not None else 99.0
        n_hi = hi if hi is not None else 99.0
        if lo < b_hi and b.min_aps < n_hi:
            raise ValidationError(
                f"Overlaps the {b.range_label} band ({b.expected_grade}) "
                f"for {qtype}{' ' + subject if subject else ''}")
    return {"qualification_type": qtype, "subject": subject, "min_aps": lo,
            "max_aps": hi, "expected_grade": exp, "meg_grade": meg,
            "source": source,
            "notes": (str(data.get("notes") or "").strip() or None)}


def add_band(data: dict[str, Any]) -> Band:
    init_db()
    p = _validate(data)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO va_benchmark_bands (qualification_type, subject,"
            " min_aps, max_aps, expected_grade, meg_grade, source,"
            " is_placeholder, notes) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (p["qualification_type"], p["subject"], p["min_aps"], p["max_aps"],
             p["expected_grade"], p["meg_grade"], p["source"], p["notes"]))
        conn.commit()
        new_id = cur.lastrowid
    return get_band(new_id)  # type: ignore[return-value]


def update_band(band_id: int, data: dict[str, Any]) -> Band:
    """Edit a band. An edited placeholder band stops being a placeholder."""
    old = get_band(band_id)
    if old is None:
        raise ValidationError(f"No benchmark band #{band_id}")
    merged = {"qualification_type": old.qualification_type,
              "subject": old.subject, "min_aps": old.min_aps,
              "max_aps": old.max_aps, "expected_grade": old.expected_grade,
              "meg_grade": old.meg_grade,
              "source": (None if old.is_placeholder else old.source),
              "notes": old.notes, **data}
    p = _validate(merged, existing_id=band_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE va_benchmark_bands SET qualification_type=?, subject=?,"
            " min_aps=?, max_aps=?, expected_grade=?, meg_grade=?, source=?,"
            " is_placeholder=0, notes=?, updated_at=datetime('now')"
            " WHERE band_id=?",
            (p["qualification_type"], p["subject"], p["min_aps"], p["max_aps"],
             p["expected_grade"], p["meg_grade"], p["source"], p["notes"],
             band_id))
        conn.commit()
    return get_band(band_id)  # type: ignore[return-value]


def delete_band(band_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM va_benchmark_bands WHERE band_id=?",
                           (int(band_id),))
        conn.commit()
        return cur.rowcount > 0


def band_for(aps: float | None, qualification_type: str | None,
             subject: str | None = None) -> Band | None:
    """The benchmark band for an average GCSE score (subject bands first)."""
    if aps is None or not qualification_type:
        return None
    bands = list_bands(qualification_type=qualification_type)
    order = [subject.strip()] if subject and subject.strip() else []
    order.append("")                      # then the all-subjects bands
    for wanted in order:
        for b in bands:
            if (b.subject or "") != wanted:
                continue
            if b.min_aps <= aps and (b.max_aps is None or aps < b.max_aps):
                return b
    return None


# ── Actual results ─────────────────────────────────────────────────

_SEASON_ORDER = {"January": 1, "Winter": 1, "Spring": 2, "May/June": 3,
                 "Summer": 3, "June": 3, "Autumn": 4, "November": 4}


def actual_results_for(student_id: str, *, released_only: bool = True
                       ) -> dict[str, ActualResult]:
    """subject -> the result that counts (latest series, best grade in it).

    Results still under embargo are left out by default.
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
        learning_aims,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results,
    )
    out: dict[str, ActualResult] = {}
    try:
        rows = exam_results.list_results(student_id=student_id,
                                         released_only=released_only)
    except Exception:
        logger.debug("results unavailable for %s", student_id, exc_info=True)
        return out
    for r in rows:
        qtype = learning_aims.qualification_type_for(student_id, r.subject)
        cand = ActualResult(subject=r.subject, grade=r.result.grade,
                            year=int(r.year), season=r.season or "",
                            qualification_type=qtype)
        cur = out.get(r.subject)
        if cur is None:
            out[r.subject] = cand
            continue
        k_new = (cand.year, _SEASON_ORDER.get(cand.season, 0))
        k_cur = (cur.year, _SEASON_ORDER.get(cur.season, 0))
        if k_new > k_cur or (k_new == k_cur and grade_scales.sort_key(
                cand.grade, qtype) < grade_scales.sort_key(cur.grade, qtype)):
            out[r.subject] = cand
    return out


# ── Derivation ─────────────────────────────────────────────────────

def _points(grade: str | None, qtype: str | None) -> int | None:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    return grade_scales.grade_points(grade, qtype) if grade else None


def derive_student(student_id: str, *, student_name: str | None = None,
                   aps: float | None = None,
                   academic_year: str | None = None) -> list[DerivedVA]:
    """Expected grade, MEG, actual grade and VA per aim for one learner.

    Withdrawn / transferred aims are left out (they are not in VA).
    ``academic_year`` keeps only aims live in that funding year.
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
        prior_attainment,
    )
    if aps is None:
        aps = prior_attainment.average_gcse_score(student_id)
    if student_name is None:
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        s = students.get_student(student_id)
        student_name = s.full_name if s else "(unknown)"
    results = actual_results_for(student_id)
    out: list[DerivedVA] = []
    for aim in learning_aims.list_aims(student_id):
        if aim.status in ("Withdrawn", "Transferred"):
            continue
        if academic_year and not _aim_in_year(aim, academic_year):
            continue
        band = band_for(aps, aim.qualification_type, aim.subject)
        res = results.get(aim.subject)
        note = ""
        if aps is None:
            note = "No GCSE results recorded"
        elif band is None:
            note = f"No benchmark band for {aim.qualification_type}"
        exp = band.expected_grade if band else None
        out.append(DerivedVA(
            student_id=student_id, student_name=student_name,
            subject=aim.subject, qualification_type=aim.qualification_type,
            aim_status=aim.status, aps=aps, expected_grade=exp,
            meg_grade=band.minimum_grade if band else None,
            actual_grade=res.grade if res else None,
            result_year=res.year if res else None,
            expected_points=_points(exp, aim.qualification_type),
            actual_points=_points(res.grade if res else None,
                                  aim.qualification_type),
            placeholder=bool(band and band.is_placeholder), note=note))
    return out


def _aim_in_year(aim: Any, academic_year: str) -> bool:
    m = re.match(r"^\s*(\d{4})", academic_year or "")
    if not m:
        return True
    y = int(m.group(1))
    start, end = f"{y}-08-01", f"{y + 1}-07-31"
    finish = aim.withdrawal_date or aim.actual_end_date or aim.planned_end_date
    return aim.start_date <= end and (finish is None or finish >= start)


def derive_cohort(*, academic_year: str | None = None,
                  subject: str | None = None,
                  results_year: int | None = None,
                  qualification_types: tuple[str, ...] | None = None,
                  active_only: bool = False) -> CohortVA:
    """VA for every learner (optionally one subject / result year).

    ``qualification_types`` limits the rows, e.g. ``("A Level",)`` for
    an A-level VA figure. Cohort and subject means use only rows with
    both an expected and an actual grade.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    out = CohortVA()
    for s in students.list_students():
        if active_only and s.status != "Active":
            continue
        try:
            rows = derive_student(s.student_id, student_name=s.full_name,
                                  academic_year=academic_year)
        except Exception:
            logger.debug("VA derivation failed for %s", s.student_id,
                         exc_info=True)
            continue
        for r in rows:
            if subject and r.subject != subject:
                continue
            if qualification_types and r.qualification_type not in qualification_types:
                continue
            if results_year is not None and r.result_year not in (None, results_year):
                continue
            out.rows.append(r)
    by: dict[str, list[DerivedVA]] = {}
    for r in out.rows:
        by.setdefault(r.subject, []).append(r)
        if r.placeholder:
            out.placeholder_in_use = True
    scored = [r.va for r in out.rows if r.va is not None]
    out.with_results = len(scored)
    out.mean_va = round(sum(scored) / len(scored), 2) if scored else None
    for subj in sorted(by):
        vals = [r.va for r in by[subj] if r.va is not None]
        out.by_subject.append(SubjectVA(
            subject=subj, learners=len(by[subj]), with_results=len(vals),
            mean_va=round(sum(vals) / len(vals), 2) if vals else None))
    return out


# ── Write-through to value-added records ───────────────────────────

@dataclass
class ApplyResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.created} created, {self.updated} updated, "
                f"{self.unchanged} unchanged, {len(self.skipped)} skipped")


def apply_to_records(exam_session: str, *,
                     rows: list[DerivedVA] | None = None,
                     academic_year: str | None = None,
                     overwrite_expected: bool = True,
                     teacher: str | None = None) -> ApplyResult:
    """Write prior attainment, expected grade (and actual grade, when the
    result is in) into ``value_added_records`` for ``exam_session``,
    through value_added's own create/update functions so its rules and
    VA recomputation apply. Rows the value-added module rejects (e.g. a
    grade outside the scale it accepts) are reported, not forced.
    """
    from education_system.systems.sixth_form.domain.assessment.value_added import (
        value_added,
    )
    if rows is None:
        rows = derive_cohort(academic_year=academic_year).rows
    out = ApplyResult()
    for r in rows:
        if r.expected_grade is None:
            out.skipped.append((r.student_id, r.subject,
                                r.note or "no expected grade"))
            continue
        try:
            existing = value_added.get_record_for(r.student_id, r.subject,
                                                  exam_session)
            if existing is None:
                value_added.create_record({
                    "student_id": r.student_id, "subject_name": r.subject,
                    "exam_session": exam_session,
                    "prior_attainment": r.aps,
                    "expected_grade": r.expected_grade,
                    "actual_grade": r.actual_grade, "teacher": teacher,
                    "notes": ("Expected grade derived from the "
                              + ("PLACEHOLDER " if r.placeholder else "")
                              + "benchmark table")})
                out.created += 1
                continue
            patch: dict[str, Any] = {}
            if existing.prior_attainment != r.aps:
                patch["prior_attainment"] = r.aps
            if r.expected_grade != existing.expected_grade and (
                    overwrite_expected or not existing.expected_grade):
                patch["expected_grade"] = r.expected_grade
            if r.actual_grade and r.actual_grade != existing.actual_grade:
                patch["actual_grade"] = r.actual_grade
            if patch:
                value_added.update_record(existing.record_id, patch)
                out.updated += 1
            else:
                out.unchanged += 1
        except (value_added.ValidationError, ValueError) as e:
            out.skipped.append((r.student_id, r.subject, str(e)))
    return out


__all__ = [
    "PLACEHOLDER_SOURCE", "ValidationError", "Band", "ActualResult",
    "DerivedVA", "SubjectVA", "CohortVA", "ApplyResult",
    "init_db", "restore_placeholder", "list_bands", "get_band",
    "placeholder_in_use", "add_band", "update_band", "delete_band",
    "band_for", "actual_results_for", "derive_student", "derive_cohort",
    "apply_to_records",
]
