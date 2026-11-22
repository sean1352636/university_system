"""Sixth-form alumni — Cross-module linking (#11-#15).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

from .models import (
    Alumnus,
    UnarchivedLeaver,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    init_db,
)


# ── Cross-module linking (#11–#15) ────────────────────────────────

def _safe_import(path: str):
    try:
        from importlib import import_module
        return import_module(path)
    except Exception:
        return None


def was_bursary_recipient(student_id: str) -> bool:
    bm = _safe_import(
        "education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries")
    if bm is None:
        return False
    try:
        approved, paid, _outstanding = bm.student_summary(student_id)
    except Exception:
        logger.debug("Bursary lookup failed for %s",
                       student_id, exc_info=True)
        return False
    return (approved or 0) > 0 or (paid or 0) > 0


def bursary_summary_for(student_id: str
                          ) -> tuple[float, float, float] | None:
    bm = _safe_import(
        "education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries")
    if bm is None:
        return None
    try:
        return bm.student_summary(student_id)
    except Exception:
        logger.debug("bursary_summary_for(%s) failed",
                       student_id, exc_info=True)
        return None


def _ucas_destination_for(student_id: str
                            ) -> tuple[str | None, int | None]:
    """Return (destination_detail, cycle_year) from the most recent
    UCAS application whose firm/insurance choice is the student's
    final destination. Best-effort."""
    um = _safe_import(
        "education_system.systems.sixth_form.domain.progression.university.ucas")
    if um is None:
        return (None, None)
    try:
        app = um.get_application_for_student(student_id)
        if app is None:
            return (None, None)
        choices = um.list_choices(app.application_id)
        firm = next((c for c in choices
                       if (c.final_decision or "").lower() == "firm"),
                      None)
        target = firm or next((c for c in choices
                                  if (c.final_decision or "").lower()
                                  == "insurance"), None)
        if target is None:
            return (None, app.cycle_year)
        detail = f"{target.university} — {target.course_name}"
        return (detail, app.cycle_year)
    except Exception:
        logger.exception("UCAS lookup failed for %s", student_id)
        return (None, None)


def _exam_results_for(student_id: str
                        ) -> list[tuple[str, str, str | None, int | None]]:
    """Return list of (subject, grade, board, year) tuples for the
    student. Empty list if exam_results module unavailable.

    Tries the modern ``results_for_student`` API first, then the
    older ``list_results`` keyword form, then the legacy
    ``list_results_with_detail`` name — accommodates schema drift
    across exam_results module versions."""
    em = _safe_import(
        "education_system.systems.sixth_form.domain."
        "exam_results.exam_results")
    if em is None:
        return []
    rows = None
    for fn_name, kwargs in (
            ("results_for_student", {"student_id": student_id}),
            ("list_results",        {"student_id": student_id}),
            ("list_results_with_detail",
                {"student_id": student_id}),
            ("list_results_with_detail", {})):
        fn = getattr(em, fn_name, None)
        if fn is None:
            continue
        try:
            rows = fn(**kwargs)
            if not kwargs:
                rows = [r for r in rows
                          if getattr(r, "student_id", None)
                              == student_id]
            break
        except TypeError:
            # Wrong kwargs for this version — try the next form.
            continue
        except Exception:
            logger.warning(
                "exam_results.%s failed for %s",
                fn_name, student_id, exc_info=True)
            return []
    if rows is None:
        return []
    out: list[tuple[str, str, str | None, int | None]] = []
    for r in rows:
        try:
            grade = (r.result.grade if r.result else None) or ""
            if not grade:
                continue
            out.append((r.subject, grade,
                         getattr(r, "exam_board", None),
                         getattr(r, "year", None)))
        except Exception:
            continue
    return out


def _career_aspiration_for(student_id: str) -> str | None:
    cm = _safe_import(
        "education_system.systems.sixth_form.domain.progression.careers.careers")
    if cm is None:
        return None
    try:
        a = cm.get_aspiration_for_student(student_id)
    except Exception:
        logger.debug("careers aspiration lookup failed for %s",
                       student_id, exc_info=True)
        return None
    if a is None:
        return None
    parts = [a.target_career, a.target_course, a.target_employer]
    return " / ".join(p for p in parts if p) or None


def archive_student_enriched(student_id: str, **kwargs) -> Alumnus:
    """Like :func:`archive_student` but first auto-fills destination
    detail from UCAS, seeds A-level results into the education table
    from exam_results, tags bursary recipients, and links any career
    aspiration in the notes. Any ``**kwargs`` accepted by
    ``archive_student`` override auto-derived values."""
    init_db()
    ucas_detail, ucas_year = _ucas_destination_for(student_id)
    aspiration = _career_aspiration_for(student_id)
    derived: dict[str, Any] = {}
    if ucas_detail and not kwargs.get("destination_detail"):
        derived["destination_detail"] = ucas_detail
        derived["destination_type"] = (kwargs.get("destination_type")
                                          or "University")
    if ucas_year and not kwargs.get("leaving_year"):
        derived["leaving_year"] = str(ucas_year)
    if aspiration and not kwargs.get("notes"):
        derived["notes"] = f"Aspiration on leaving: {aspiration}"
    payload = {**derived, **kwargs}
    a = archive_student(student_id, **payload)
    # Seed A-level results into education history
    existing_edu = list_education(a.alumni_id)
    if not existing_edu:
        for subject, grade, board, year in _exam_results_for(student_id):
            try:
                add_education(a.alumni_id, {
                    "qualification": "A-Level",
                    "subject":       subject,
                    "institution":   board or "Sixth Form",
                    "end_date":      f"{year}-08-31" if year else None,
                    "grade":         grade,
                    "status":        "Completed",
                })
            except ValidationError:
                continue
    # Tag bursary recipients
    if was_bursary_recipient(student_id):
        try:
            add_tag(a.alumni_id, "Bursary recipient")
        except Exception:
            logger.exception("Failed to tag bursary recipient #%d",
                              a.alumni_id)
    _log_action("alumnus.archive_enriched",
                  alumni_id=a.alumni_id, student_id=student_id,
                  destination=a.destination_type,
                  edu_rows=len(list_education(a.alumni_id)))
    return a


def alumnus_for_student(student_id: str) -> Alumnus | None:
    """Alias of :func:`get_alumnus_by_original_id` — intended for
    use from the students module to show 'this student became
    alumnus #N' on their profile."""
    return get_alumnus_by_original_id(student_id)


def find_unarchived_leavers() -> list[UnarchivedLeaver]:
    """Return current students who look like leavers — i.e. either
    have a UCAS application with a final decision, or recorded
    A-level (i.e. exam) results from a past summer — but no alumni
    row yet. Sort by oldest cycle/exam year first."""
    init_db()
    sm = _safe_import(
        "education_system.systems.sixth_form.domain.learners.students.students")
    if sm is None:
        return []
    try:
        students = sm.list_students()
    except Exception:
        logger.warning("students.list_students() failed",
                         exc_info=True)
        return []
    out: list[UnarchivedLeaver] = []
    today_year = _dt.date.today().year
    for s in students:
        if get_alumnus_by_original_id(s.student_id) is not None:
            continue
        detail, cycle = _ucas_destination_for(s.student_id)
        exams = _exam_results_for(s.student_id)
        last_year = max((y for _, _, _, y in exams if y), default=None)
        is_leaver = False
        if detail and cycle and cycle <= today_year:
            is_leaver = True
        if last_year and last_year < today_year:
            is_leaver = True
        if not is_leaver:
            continue
        out.append(UnarchivedLeaver(
            student_id=s.student_id, full_name=s.full_name,
            email=getattr(s, "email", None),
            ucas_cycle_year=cycle, final_destination=detail,
            last_exam_year=last_year))
    out.sort(key=lambda x: (x.ucas_cycle_year or x.last_exam_year
                              or today_year, x.student_id))
    return out


@dataclass
class CareerAdviceRow:
    destination_type: str
    detail: str
    sector: str | None
    count: int


def destinations_for_advice(*, subject: str | None = None,
                              sector: str | None = None,
                              limit: int = 25
                              ) -> list[CareerAdviceRow]:
    """Aggregate alumni destinations for use by the careers module
    when advising current students. If ``subject`` is given, restrict
    to alumni who studied that A-level subject (joining via the
    education history). If ``sector`` is given, restrict to alumni
    now working in that sector."""
    init_db()
    args: list[Any] = []
    join = ""
    where = ["a.status != 'Deceased'", "a.destination_type != 'Unknown'"]
    if subject:
        join = ("JOIN alumni_education e ON e.alumni_id = a.alumni_id "
                 "AND e.qualification = 'A-Level' "
                 "AND e.subject = ? COLLATE NOCASE ")
        args.append(subject)
    if sector:
        where.append("a.current_sector = ?")
        args.append(sector)
    sql = (f"SELECT a.destination_type AS d, "
            f"COALESCE(a.destination_detail, '—') AS detail, "
            f"a.current_sector AS sector, COUNT(*) AS n "
            f"FROM alumni a {join}"
            f"WHERE {' AND '.join(where)} "
            f"GROUP BY a.destination_type, a.destination_detail, "
            f"a.current_sector "
            f"ORDER BY n DESC LIMIT ?")
    args.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [CareerAdviceRow(
        destination_type=r["d"], detail=r["detail"],
        sector=r["sector"], count=r["n"]) for r in rows]


# ══ Engagement & programmes ══════════════════════════════════════
#
# Money is stored in pence to keep totals exact. Helpers below
# accept either pounds (float, will be rounded to nearest penny) or
# pence (int) — see ``_money_in``.


def _pounds_to_pence(value: Any, label: str, *,
                       allow_zero: bool = False,
                       required: bool = True) -> int:
    """Coerce a money amount expressed in *pounds* to integer pence.
    Accepts ``int``/``float`` (pounds) or ``str`` (with optional
    leading £ and commas). Always multiplies by 100."""
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return 0
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a number")
    s = str(value).strip().lstrip("£").replace(",", "")
    try:
        pence = round(float(s) * 100)
    except ValueError:
        raise ValidationError(f"{label} is not a valid amount") \
            from None
    if pence < 0:
        raise ValidationError(f"{label} cannot be negative")
    if not allow_zero and pence == 0:
        raise ValidationError(f"{label} must be greater than zero")
    return pence


def _resolve_money(payload: dict[str, Any],
                     pence_key: str, pounds_key: str,
                     label: str, *,
                     allow_zero: bool = False,
                     required: bool = True) -> int:
    """Read a money amount from either ``<pence_key>`` (raw integer
    pence) or ``<pounds_key>`` (pounds, float-ish). Pence wins if
    both are supplied."""
    if payload.get(pence_key) not in (None, ""):
        try:
            p = int(payload[pence_key])
        except (TypeError, ValueError):
            raise ValidationError(
                f"{label} (pence) must be an integer") from None
        if p < 0:
            raise ValidationError(f"{label} cannot be negative")
        if not allow_zero and p == 0:
            raise ValidationError(
                f"{label} must be greater than zero")
        return p
    return _pounds_to_pence(payload.get(pounds_key), label,
                              allow_zero=allow_zero,
                              required=required)


def _money_out(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    archive_student,
    get_alumnus_by_original_id,
)
from .profile import (  # noqa: E402,F401
    add_education,
    add_tag,
    list_education,
)
