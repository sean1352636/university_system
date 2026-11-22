"""UCAS tariff calculation from A-level grades.

A small, pure module shared by both the CLI and GUI student-create flows so
the points table and validation live in exactly one place.
"""

from __future__ import annotations

# UCAS tariff points for A-level grades (2017+ tariff).
ALEVEL_POINTS: dict[str, int] = {
    "A*": 56,
    "A": 48,
    "B": 40,
    "C": 32,
    "D": 24,
    "E": 16,
}

# Grades offered in pickers, best first.
GRADE_CHOICES: list[str] = ["A*", "A", "B", "C", "D", "E"]


def normalise_grade(grade: str) -> str:
    """Return a canonical grade token ('a*' -> 'A*'), or '' if invalid."""
    g = (grade or "").strip().upper().replace("STAR", "*")
    return g if g in ALEVEL_POINTS else ""


def grade_points(grade: str) -> int:
    """Points for a single A-level grade (0 if unrecognised)."""
    return ALEVEL_POINTS.get(normalise_grade(grade), 0)


def compute_tariff(grades) -> int:
    """Total UCAS tariff for an iterable of A-level grades."""
    return sum(grade_points(g) for g in grades)


def format_qualifications(pairs) -> str:
    """Render [(subject, grade), ...] as 'Maths:A, Physics:B' for storage."""
    out = []
    for subject, grade in pairs:
        subject = (subject or "").strip() or "A-level"
        out.append(f"{subject}:{normalise_grade(grade) or grade}")
    return ", ".join(out)


# Level 3 qualifications other than A levels, on the same UCAS tariff
# (2017+). Keyed by the qualification's name as shown in pickers; the grade
# lists are best first. A levels come from ALEVEL_POINTS above.
QUALIFICATION_POINTS: dict[str, dict[str, int]] = {
    "A level": ALEVEL_POINTS,
    "AS level": {"A": 20, "B": 16, "C": 12, "D": 10, "E": 6},
    "Extended Project (EPQ)": {"A*": 28, "A": 24, "B": 20, "C": 16, "D": 12, "E": 8},
    "BTEC Extended Diploma": {
        "D*D*D*": 168, "D*D*D": 160, "D*DD": 152, "DDD": 144, "DDM": 128,
        "DMM": 112, "MMM": 96, "MMP": 80, "MPP": 64, "PPP": 48},
    "BTEC Diploma": {"D*D*": 112, "D*D": 104, "DD": 96, "DM": 80, "MM": 64, "MP": 48,
                     "PP": 32},
    "BTEC Foundation Diploma": {"D*": 84, "D": 72, "M": 48, "P": 24},
    "BTEC Extended Certificate": {"D*": 56, "D": 48, "M": 32, "P": 16},
    "T Level": {"Distinction*": 168, "Distinction": 144, "Merit": 120,
                "Pass (C or above)": 96, "Pass (D or E)": 72},
}

#: Qualification types offered in pickers, A level first.
QUALIFICATION_TYPES: list[str] = list(QUALIFICATION_POINTS)


def grades_for(qualification_type: str) -> list[str]:
    """The grades a qualification type can be awarded, best first."""
    return list(QUALIFICATION_POINTS.get(qualification_type or "A level", {}))


def qualification_points(qualification_type: str, grade: str) -> int:
    """Tariff points for one qualification (0 if the grade isn't one of its)."""
    qtype = qualification_type or "A level"
    if qtype == "A level":
        return grade_points(grade)
    table = QUALIFICATION_POINTS.get(qtype, {})
    wanted = (grade or "").strip().upper()
    return next((pts for g, pts in table.items() if g.upper() == wanted), 0)


def compute_tariff_entries(entries) -> int:
    """Total UCAS tariff for ``[(type, subject, grade), ...]`` — any mix of
    A levels, AS levels, EPQ, BTECs and T Levels, as many as were taken."""
    return sum(qualification_points(qtype, grade) for qtype, _subject, grade in entries)


def format_qualification_entries(entries) -> str:
    """Render ``[(type, subject, grade), ...]`` for storage, e.g.
    'A level Maths:A, BTEC Extended Certificate Sport:D'. A levels keep the
    old 'Maths:A' form so existing readers of the text are unchanged."""
    out = []
    for qtype, subject, grade in entries:
        qtype = qtype or "A level"
        subject = (subject or "").strip()
        if qtype == "A level":
            out.append(f"{subject or 'A-level'}:{normalise_grade(grade) or grade}")
        else:
            out.append(f"{qtype}{' ' + subject if subject else ''}:{grade}")
    return ", ".join(out)


def prompt_alevels_cli(num: int = 3):
    """Interactively collect ``num`` A-levels at the CLI.

    Returns a tuple ``(pairs, tariff)`` where ``pairs`` is a list of
    ``(subject, grade)`` and ``tariff`` is the computed UCAS total.
    """
    print("\nEnter your sixth-form A-level results (used to check course eligibility):")
    print(f"  Valid grades: {', '.join(GRADE_CHOICES)}")
    pairs: list[tuple[str, str]] = []
    for i in range(1, num + 1):
        subject = input(f"  A-level {i} subject: ").strip() or f"A-level {i}"
        while True:
            grade = normalise_grade(input(f"  A-level {i} grade ({subject}): "))
            if grade:
                break
            print(f"    Invalid grade. Choose one of: {', '.join(GRADE_CHOICES)}")
        pairs.append((subject, grade))
    tariff = compute_tariff(g for _, g in pairs)
    print(f"\n  -> UCAS tariff: {tariff} points "
          f"({', '.join(f'{s} {g}' for s, g in pairs)})")
    return pairs, tariff
