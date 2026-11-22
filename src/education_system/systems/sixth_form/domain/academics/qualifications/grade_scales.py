"""Grade scales for every qualification type the sixth form offers.

Results, the gradebook, predicted grades, value added and EPQ used to
accept A*-U only, which shut out BTEC, T Level, GCSE resits and Core
Maths. Every grade check now goes through :func:`validate_grade` with
the qualification type of the learning aim being graded.

Grades are listed best first. ``points`` is a simple ordinal (higher is
better) used for comparing grades and averaging within one scale; it is
not a DfE or UCAS tariff.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeScale:
    key: str
    label: str
    grades: tuple[str, ...]          # best first
    fail_grades: tuple[str, ...] = ()

    def points(self, grade: str) -> int | None:
        """Ordinal points for *grade* (best = highest), None if unknown."""
        try:
            return len(self.grades) - self.grades.index(grade)
        except ValueError:
            return None

    def is_pass(self, grade: str) -> bool:
        return grade in self.grades and grade not in self.fail_grades


_A_LEVEL = ("A*", "A", "B", "C", "D", "E", "U")
_AS_LEVEL = ("A", "B", "C", "D", "E", "U")
_GCSE = ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U")
_BTEC_SINGLE = ("D*", "D", "M", "P", "U")
_BTEC_DOUBLE = ("D*D*", "D*D", "DD", "DM", "MM", "MP", "PP", "U")
_BTEC_TRIPLE = ("D*D*D*", "D*D*D", "D*DD", "DDD", "DDM", "DMM", "MMM",
                "MMP", "MPP", "PPP", "U")
_BTEC_UNIT = ("D", "M", "P", "U")
_T_LEVEL_OVERALL = ("Distinction*", "Distinction", "Merit", "Pass",
                    "Partial achievement", "Unclassified")
_T_LEVEL_CORE = ("A*", "A", "B", "C", "D", "E", "U")
_T_LEVEL_SPECIALISM = ("Distinction", "Merit", "Pass", "Unclassified")

SCALES: dict[str, GradeScale] = {s.key: s for s in (
    GradeScale("a_level", "A level", _A_LEVEL, ("U",)),
    GradeScale("as_level", "AS level", _AS_LEVEL, ("U",)),
    GradeScale("epq", "Extended Project (EPQ)", _A_LEVEL, ("U",)),
    GradeScale("core_maths", "Core Maths (Level 3 maths)", _AS_LEVEL, ("U",)),
    GradeScale("gcse", "GCSE (9-1)", _GCSE, ("U",)),
    GradeScale("btec_single", "BTEC / vocational single award", _BTEC_SINGLE, ("U",)),
    GradeScale("btec_double", "BTEC / vocational double award", _BTEC_DOUBLE, ("U",)),
    GradeScale("btec_triple", "BTEC / vocational triple award", _BTEC_TRIPLE, ("U",)),
    GradeScale("btec_unit", "BTEC unit", _BTEC_UNIT, ("U",)),
    GradeScale("t_level", "T Level (overall)", _T_LEVEL_OVERALL,
               ("Unclassified",)),
    GradeScale("t_level_core", "T Level core component", _T_LEVEL_CORE, ("U",)),
    GradeScale("t_level_specialism", "T Level occupational specialism",
               _T_LEVEL_SPECIALISM, ("Unclassified",)),
    GradeScale("functional_skills", "Functional Skills", ("Pass", "Fail"),
               ("Fail",)),
)}

#: Qualification type -> grade scale key. Learning aims store the type.
QUALIFICATION_TYPES: dict[str, str] = {
    "A Level": "a_level",
    "AS Level": "as_level",
    "EPQ": "epq",
    "Core Maths": "core_maths",
    "GCSE": "gcse",
    "BTEC Extended Certificate": "btec_single",
    "BTEC Diploma": "btec_double",
    "BTEC Extended Diploma": "btec_triple",
    "Applied General (single)": "btec_single",
    "T Level": "t_level",
    "Functional Skills": "functional_skills",
}

DEFAULT_QUALIFICATION_TYPE = "A Level"

#: Every grade on any scale, deduplicated, for loose filters.
ALL_GRADES: tuple[str, ...] = tuple(dict.fromkeys(
    g for s in SCALES.values() for g in s.grades))


def scale_for(qualification_type: str | None) -> GradeScale:
    """The scale for a qualification type (or scale key); A level by default."""
    if not qualification_type:
        return SCALES["a_level"]
    if qualification_type in SCALES:
        return SCALES[qualification_type]
    key = QUALIFICATION_TYPES.get(qualification_type)
    if key is None:
        lowered = qualification_type.strip().lower()
        for name, k in QUALIFICATION_TYPES.items():
            if name.lower() == lowered:
                key = k
                break
    if key is None:
        raise ValueError(f"Unknown qualification type: {qualification_type!r}")
    return SCALES[key]


def validate_grade(grade: str, qualification_type: str | None = None) -> str:
    """Return *grade* normalised, or raise ValueError naming the valid grades."""
    scale = scale_for(qualification_type)
    g = (grade or "").strip()
    if g in scale.grades:
        return g
    for candidate in scale.grades:
        if candidate.lower() == g.lower():
            return candidate
    raise ValueError(
        f"Grade for {scale.label} must be one of: {', '.join(scale.grades)}")


def compare(a: str, b: str, qualification_type: str | None = None) -> int:
    """-1 / 0 / 1 as grade *a* is worse / equal / better than *b*."""
    scale = scale_for(qualification_type)
    pa, pb = scale.points(a), scale.points(b)
    if pa is None or pb is None:
        raise ValueError("Both grades must be on the same scale")
    return (pa > pb) - (pa < pb)


# ── Helpers added for learning aims, gradebook and results ──────────

#: Qualification types whose learning aims mirror into the legacy
#: ``students.subject_1..3`` slots (see ``learning_aims.sync_mirror``).
A_LEVEL_TYPES: tuple[str, ...] = ("A Level", "AS Level")

#: Scales whose grades are the A*-E letters, so the gradebook's
#: per-assignment A*/A/B/C/D/E raw-mark overrides still make sense.
LETTER_BOUNDARY_SCALES: frozenset[str] = frozenset(
    {"a_level", "as_level", "epq", "core_maths", "t_level_core"})


def canonical_type(qualification_type: str | None) -> str | None:
    """The ``QUALIFICATION_TYPES`` key for a name (case-insensitive), or None."""
    if not qualification_type:
        return None
    q = qualification_type.strip()
    if q in QUALIFICATION_TYPES:
        return q
    for name in QUALIFICATION_TYPES:
        if name.lower() == q.lower():
            return name
    return None


def is_valid_grade(grade: str | None, qualification_type: str | None = None) -> bool:
    try:
        validate_grade(grade or "", qualification_type)
        return True
    except ValueError:
        return False


def grade_points(grade: str | None, qualification_type: str | None = None) -> int | None:
    """Ordinal points on the type's scale with the fail grade at 0.

    For A level this is exactly the old value-added table
    (A*=6 ... E=1, U=0), so A-level aggregates do not move.
    """
    if not grade:
        return None
    scale = scale_for(qualification_type)
    try:
        g = validate_grade(grade, qualification_type)
    except ValueError:
        return None
    p = scale.points(g)
    return None if p is None else p - 1


def sort_key(grade: str | None, qualification_type: str | None = None) -> float:
    """Sort key putting the best grade first, across mixed scales.

    With a known type the grade's position on that scale is used. With
    no type the grade is looked up on the A-level scale first (so A*-U
    sorts exactly as ``LETTER_GRADES`` always did) and then on every
    other scale, normalised to 0..1 so a BTEC D* and an A* sit together.
    Unknown grades sort last.
    """
    if not grade:
        return 99.0
    scales: list[GradeScale] = []
    if qualification_type:
        try:
            scales.append(scale_for(qualification_type))
        except ValueError:
            pass
    scales.append(SCALES["a_level"])
    scales.extend(SCALES.values())
    for scale in scales:
        if grade in scale.grades:
            idx = scale.grades.index(grade)
            return idx / max(1, len(scale.grades) - 1)
    return 99.0


def is_pass(grade: str | None, qualification_type: str | None = None) -> bool:
    """Pass on the type's scale; with no type, any non-fail known grade."""
    if not grade:
        return False
    if qualification_type:
        try:
            return scale_for(qualification_type).is_pass(grade)
        except ValueError:
            return False
    if grade in SCALES["a_level"].grades:
        return SCALES["a_level"].is_pass(grade)
    return any(s.is_pass(grade) for s in SCALES.values() if grade in s.grades)


# Default percentage boundaries for converting an internally marked
# piece of work into a working grade. These are the college's own
# teacher-assessment defaults, NOT awarding-body boundaries. A level keeps
# the thresholds the gradebook always used (90/80/70/60/50/40); GCSE uses
# ten-point steps; every other scale spreads its passing grades evenly
# between 90% and 40%.
_PERCENT_BOUNDARIES: dict[str, tuple[tuple[str, float], ...]] = {
    "a_level": (("A*", 90.0), ("A", 80.0), ("B", 70.0), ("C", 60.0),
                ("D", 50.0), ("E", 40.0)),
    "gcse": (("9", 90.0), ("8", 80.0), ("7", 70.0), ("6", 60.0),
             ("5", 50.0), ("4", 40.0), ("3", 30.0), ("2", 20.0),
             ("1", 10.0)),
}


def percent_boundaries(qualification_type: str | None = None
                       ) -> tuple[tuple[str, float], ...]:
    """(grade, minimum %) best first, excluding the fail grade."""
    scale = scale_for(qualification_type)
    if scale.key in _PERCENT_BOUNDARIES:
        return _PERCENT_BOUNDARIES[scale.key]
    if scale.key in LETTER_BOUNDARY_SCALES:
        # Same letters as A level (AS / Core Maths drop A*).
        return tuple((g, t) for g, t in _PERCENT_BOUNDARIES["a_level"]
                     if g in scale.grades)
    passing = [g for g in scale.grades if g not in scale.fail_grades]
    if not passing:
        return ()
    if len(passing) == 1:
        return ((passing[0], 50.0),)
    step = 50.0 / (len(passing) - 1)
    return tuple((g, round(90.0 - i * step, 1)) for i, g in enumerate(passing))


def percent_to_grade(pct: float | None, qualification_type: str | None = None
                     ) -> str | None:
    """Working grade for a percentage on the type's scale (None if pct is None)."""
    if pct is None:
        return None
    for grade, threshold in percent_boundaries(qualification_type):
        if pct >= threshold:
            return grade
    scale = scale_for(qualification_type)
    return scale.fail_grades[0] if scale.fail_grades else scale.grades[-1]


def grades_for(qualification_type: str | None = None) -> tuple[str, ...]:
    """The grade list (best first) for a type; A*-U when unknown."""
    try:
        return scale_for(qualification_type).grades
    except ValueError:
        return SCALES["a_level"].grades
