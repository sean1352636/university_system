"""Qualification grade ladders and UCAS Tariff points, for every system.

The university's results day had only the A level letters A*–E, so an
applicant with a BTEC, a T Level, an EPQ or an AS on their offer never got
a verdict and sat at Pending for ever. The sixth form knows every
qualification it teaches (``sixth_form.domain.academics.qualifications.
grade_scales``), but systems never import each other, so the ladders are
mirrored here in a form either side can use: the same scale keys, the same
grades in the same best-first order, the same qualification type names.
Keep the two in step — if the sixth form adds a scale, add it here too.

**UCAS Tariff points.** :data:`TARIFF_POINTS` holds the published UCAS
Tariff (the 2017 tariff, in use for entry from 2017 onwards) for the
qualifications whose values are certain:

* GCE A level: A* 56, A 48, B 40, C 32, D 24, E 16
* GCE AS level: A 20, B 16, C 12, D 10, E 6
* Extended Project (EPQ): A* 28, A 24, B 20, C 16, D 12, E 8
* Core Maths (Level 3 Certificate in Mathematical Studies): as AS level,
  A 20, B 16, C 12, D 10, E 6
* BTEC National Extended Certificate / A-level-sized Applied General
  (single award): D* 56, D 48, M 32, P 16
* BTEC National Diploma (double award): D*D* 112, D*D 104, DD 96, DM 80,
  MM 64, MP 48, PP 32
* BTEC National Extended Diploma (triple award): D*D*D* 168, D*D*D 160,
  D*DD 152, DDD 144, DDM 128, DMM 112, MMM 96, MMP 80, MPP 64, PPP 48
* T Level (overall): Distinction* 168, Distinction 144, Merit 120

Source: UCAS, "UCAS Tariff tables" (ucas.com, Tariff 2017 onwards).

Deliberately left out:

* **T Level Pass** — UCAS gives it 96 points with a core component of C or
  above and 72 with D or E, and an overall grade on its own does not say
  which. :func:`tariff_points` returns ``None`` (unknown) unless the core
  grade is supplied.
* **BTEC unit grades, T Level core / specialism component grades** — the
  tariff is awarded for the whole qualification, not its parts.
* **GCSE and Functional Skills** — they carry no UCAS Tariff points.
* Fail grades (U / Unclassified / Partial achievement) score nothing, which
  is the tariff's answer rather than a guess.
* Any other qualification (Scottish Highers, IB, Cambridge Pre-U, music
  grades …) — not taught by any system on this platform; a result in one
  is "points unknown" and a caller treats it as needing a person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "LADDERS",
    "QUALIFICATION_TYPES",
    "TARIFF_POINTS",
    "TARIFF_SOURCE",
    "Ladder",
    "canonical_type",
    "infer_type",
    "ladder_for",
    "meets",
    "normalise_grade",
    "rank",
    "scale_key",
    "tariff_points",
]

TARIFF_SOURCE = "UCAS Tariff tables (2017 Tariff), ucas.com"


@dataclass(frozen=True)
class Ladder:
    """One grade scale, best first. Mirrors the sixth form's GradeScale."""

    key: str
    label: str
    grades: tuple[str, ...]
    fail_grades: tuple[str, ...] = ()

    def rank(self, grade: str) -> int | None:
        """0 for the best grade, rising; ``None`` if not on this ladder."""
        try:
            return self.grades.index(grade)
        except ValueError:
            return None

    def normalise(self, grade: str | None) -> str | None:
        g = str(grade or "").strip()
        if not g:
            return None
        if g in self.grades:
            return g
        squashed = g.replace(" ", "").lower()
        for candidate in self.grades:
            if candidate.replace(" ", "").lower() == squashed:
                return candidate
        return None


# Ladders: identical keys, labels and order to the sixth form's grade_scales.
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

LADDERS: dict[str, Ladder] = {s.key: s for s in (
    Ladder("a_level", "A level", _A_LEVEL, ("U",)),
    Ladder("as_level", "AS level", _AS_LEVEL, ("U",)),
    Ladder("epq", "Extended Project (EPQ)", _A_LEVEL, ("U",)),
    Ladder("core_maths", "Core Maths (Level 3 maths)", _AS_LEVEL, ("U",)),
    Ladder("gcse", "GCSE (9-1)", _GCSE, ("U",)),
    Ladder("btec_single", "BTEC / vocational single award", _BTEC_SINGLE, ("U",)),
    Ladder("btec_double", "BTEC / vocational double award", _BTEC_DOUBLE, ("U",)),
    Ladder("btec_triple", "BTEC / vocational triple award", _BTEC_TRIPLE, ("U",)),
    Ladder("btec_unit", "BTEC unit", _BTEC_UNIT, ("U",)),
    Ladder("t_level", "T Level (overall)", _T_LEVEL_OVERALL,
           ("Partial achievement", "Unclassified")),
    Ladder("t_level_core", "T Level core component", _T_LEVEL_CORE, ("U",)),
    Ladder("t_level_specialism", "T Level occupational specialism",
           _T_LEVEL_SPECIALISM, ("Unclassified",)),
    Ladder("functional_skills", "Functional Skills", ("Pass", "Fail"),
           ("Fail",)),
)}

#: Qualification type name -> ladder key. The names are the sixth form's.
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

#: Other spellings an offer letter or another system uses for the same
#: qualification. Compared lower-case with spaces, dots and hyphens removed.
_ALIASES: dict[str, str] = {
    "alevel": "A Level", "alevels": "A Level", "gcealevel": "A Level",
    "a2": "A Level", "al": "A Level",
    "aslevel": "AS Level", "as": "AS Level", "gceas": "AS Level",
    "gceaslevel": "AS Level",
    "epq": "EPQ", "extendedproject": "EPQ",
    "extendedprojectqualification": "EPQ",
    "coremaths": "Core Maths", "coremathematics": "Core Maths",
    "mathematicalstudies": "Core Maths",
    "gcse": "GCSE", "gcses": "GCSE", "gcse(91)": "GCSE",
    "btecextendedcertificate": "BTEC Extended Certificate",
    "btecnationalextendedcertificate": "BTEC Extended Certificate",
    "extendedcertificate": "BTEC Extended Certificate",
    "btecsubsidiarydiploma": "BTEC Extended Certificate",
    "btecdiploma": "BTEC Diploma", "btecnationaldiploma": "BTEC Diploma",
    "diploma": "BTEC Diploma",
    "btecextendeddiploma": "BTEC Extended Diploma",
    "btecnationalextendeddiploma": "BTEC Extended Diploma",
    "extendeddiploma": "BTEC Extended Diploma",
    "appliedgeneral": "Applied General (single)",
    "appliedgeneral(single)": "Applied General (single)",
    "tlevel": "T Level", "tlevels": "T Level",
    "functionalskills": "Functional Skills",
}


def _squash(text: str) -> str:
    return re.sub(r"[\s.\-_]", "", text.lower())


def canonical_type(qualification_type: str | None) -> str | None:
    """The canonical qualification type name, or ``None`` if unknown.

    Accepts the sixth form's names, ladder keys ("btec_triple") and the
    usual offer-letter spellings ("A-level", "Extended Diploma").
    """
    if not qualification_type:
        return None
    q = str(qualification_type).strip()
    if q in QUALIFICATION_TYPES:
        return q
    for name in QUALIFICATION_TYPES:
        if name.lower() == q.lower():
            return name
    if q in LADDERS:
        for name, key in QUALIFICATION_TYPES.items():
            if key == q:
                return name
    return _ALIASES.get(_squash(q))


def scale_key(qualification_type: str | None) -> str | None:
    """The ladder key for a qualification type (or a key itself)."""
    if qualification_type and qualification_type in LADDERS:
        return qualification_type
    name = canonical_type(qualification_type)
    return QUALIFICATION_TYPES.get(name) if name else None


def ladder_for(qualification_type: str | None) -> Ladder | None:
    key = scale_key(qualification_type)
    return LADDERS.get(key) if key else None


def normalise_grade(grade: str | None,
                    qualification_type: str | None) -> str | None:
    """*grade* as written on the type's ladder, or ``None`` if not on it."""
    ladder = ladder_for(qualification_type)
    return ladder.normalise(grade) if ladder else None


def rank(grade: str | None, qualification_type: str | None) -> int | None:
    """0 for the best grade on the type's ladder; ``None`` if unknown."""
    ladder = ladder_for(qualification_type)
    if ladder is None:
        return None
    g = ladder.normalise(grade)
    return ladder.rank(g) if g else None


def meets(achieved: str | None, required: str | None,
          qualification_type: str | None) -> bool | None:
    """Is *achieved* at least *required* on the type's ladder?

    ``None`` when either grade is not on that ladder — unknown is not no.
    """
    ra = rank(achieved, qualification_type)
    rr = rank(required, qualification_type)
    if ra is None or rr is None:
        return None
    return ra <= rr


_BTEC_COMPOSITE_RE = re.compile(r"^(?:D\*|D|M|P){1,3}$")
_GCSE_RE = re.compile(r"^[1-9]$")


def infer_type(grade: str | None) -> str | None:
    """Best guess at the qualification behind a bare grade.

    Used only where a result arrives without its qualification type.
    ``A*``–``E`` is taken as A level, a composite of D*/D/M/P with a merit
    or pass in it (or a D*) as the BTEC of that size, a T Level word as a
    T Level, a single digit as GCSE. Ambiguous grades ("D", "DD", "DDD")
    are read as A level, which is what they mean in every letter this
    platform sends.
    """
    g = str(grade or "").strip()
    if not g:
        return None
    if g.upper() in ("A*", "A", "B", "C", "D", "E", "U"):
        return "A Level"
    if _GCSE_RE.match(g):
        return "GCSE"
    up = g.upper().replace(" ", "")
    if _BTEC_COMPOSITE_RE.match(up):
        size = len(re.findall(r"D\*|D|M|P", up))
        if set(up.replace("*", "")) <= {"D"} and "*" not in up:
            return "A Level"
        return {1: "BTEC Extended Certificate", 2: "BTEC Diploma",
                3: "BTEC Extended Diploma"}[size]
    if LADDERS["t_level"].normalise(g):
        return "T Level"
    return None


#: Published UCAS Tariff points, keyed by ladder key then grade. See the
#: module docstring for the source and for what is deliberately absent.
TARIFF_POINTS: dict[str, dict[str, int]] = {
    "a_level": {"A*": 56, "A": 48, "B": 40, "C": 32, "D": 24, "E": 16},
    "as_level": {"A": 20, "B": 16, "C": 12, "D": 10, "E": 6},
    "epq": {"A*": 28, "A": 24, "B": 20, "C": 16, "D": 12, "E": 8},
    "core_maths": {"A": 20, "B": 16, "C": 12, "D": 10, "E": 6},
    "btec_single": {"D*": 56, "D": 48, "M": 32, "P": 16},
    "btec_double": {"D*D*": 112, "D*D": 104, "DD": 96, "DM": 80,
                    "MM": 64, "MP": 48, "PP": 32},
    "btec_triple": {"D*D*D*": 168, "D*D*D": 160, "D*DD": 152, "DDD": 144,
                    "DDM": 128, "DMM": 112, "MMM": 96, "MMP": 80,
                    "MPP": 64, "PPP": 48},
    "t_level": {"Distinction*": 168, "Distinction": 144, "Merit": 120},
}

#: Scales whose results carry no tariff at all (as opposed to unknown).
_NO_TARIFF = frozenset({"gcse", "functional_skills", "btec_unit",
                        "t_level_core", "t_level_specialism"})


def tariff_points(qualification_type: str | None, grade: str | None, *,
                  t_level_core_grade: str | None = None) -> int | None:
    """UCAS Tariff points for a result, ``0`` for a fail or a qualification
    with no tariff, ``None`` when the value is not known here.

    A T Level Pass scores 96 with a core component at C or above and 72
    with D or E (UCAS); pass the core grade to get it, otherwise ``None``.
    """
    key = scale_key(qualification_type)
    if key is None:
        return None
    ladder = LADDERS[key]
    g = ladder.normalise(grade)
    if g is None:
        return None
    if key in _NO_TARIFF or g in ladder.fail_grades:
        return 0
    if key == "t_level" and g == "Pass":
        core = LADDERS["t_level_core"].normalise(t_level_core_grade)
        if core in ("A*", "A", "B", "C"):
            return 96
        if core in ("D", "E"):
            return 72
        return None
    return TARIFF_POINTS.get(key, {}).get(g)


def is_tariff_bearing(qualification_type: str | None) -> bool:
    """Does this qualification count towards a tariff total at all?"""
    key = scale_key(qualification_type)
    return key is not None and key not in _NO_TARIFF
