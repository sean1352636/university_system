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
