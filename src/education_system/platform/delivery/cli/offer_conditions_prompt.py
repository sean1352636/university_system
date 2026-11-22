"""Shared CLI prompts for structured UCAS offer conditions.

Used by the university's decision flow and the sixth form's offer editor,
which both store conditions in the platform's shape
(``platform/cross_system/offer_conditions``). The caller passes its own
``ask(prompt, default="", allow_empty=True)`` so cancel handling stays the
caller's (its abort exception simply propagates).
"""

from __future__ import annotations

from typing import Any, Callable

from education_system.platform.cross_system import offer_conditions as oc
from education_system.platform.cross_system import qualification_grades as qg

__all__ = ["ask_condition", "conditions_flow", "print_conditions"]

Ask = Callable[..., str]


def print_conditions(rows: list[dict[str, Any]], *, indent: str = "    ") -> None:
    if not rows:
        print(f"{indent}(none — the grade requirement text is read instead)")
    for i, c in enumerate(rows, 1):
        print(f"{indent}{i:>2}) [{oc.KIND_LABELS.get(c['kind'], c['kind'])}] "
              f"{oc.describe(c)}")


def ask_condition(ask: Ask) -> dict[str, Any]:
    """Prompt for one condition; raises ``ValueError`` if it is invalid."""
    kinds = list(oc.CONDITION_KINDS)
    print("\n    Condition kinds:")
    for i, k in enumerate(kinds, 1):
        print(f"      {i}) {oc.KIND_LABELS[k]}")
    raw = ask("Kind #", allow_empty=False)
    if not raw.isdigit() or not 1 <= int(raw) <= len(kinds):
        raise ValueError("Pick a kind by its number")
    kind = kinds[int(raw) - 1]
    row: dict[str, Any] = {"kind": kind}
    if kind == "other_text":
        row["text"] = ask("Condition text", allow_empty=False)
    elif kind == "tariff_points":
        row["min_points"] = ask("Minimum UCAS Tariff points", allow_empty=False)
        row["count"] = ask("Best N results only (blank = all)")
        row["qualification_type"] = ask("Only from qualification type (blank = any)")
    elif kind == "gcse_requirement":
        row["subject"] = ask("GCSE subject(s) (e.g. English and Maths)",
                             allow_empty=False)
        row["min_grade"] = ask("Minimum grade (9-1)", allow_empty=False)
    else:
        print("    Qualification types: " + ", ".join(qg.QUALIFICATION_TYPES))
        row["qualification_type"] = ask(
            "Qualification type",
            default=("EPQ" if kind == "qualification_grade" else ""))
        if kind == "subject_grade":
            row["subject"] = ask("Subject (alternatives with '/' or 'or')",
                                 allow_empty=False)
            row["count"] = ask("How many of those subjects (blank = 1)")
        elif kind == "qualification_grade":
            row["subject"] = ask("Subject (optional)")
        row["min_grade"] = ask(
            "Grades (e.g. ABB, D*DD, BB + DM)" if kind == "grade_profile"
            else "Minimum grade", allow_empty=False)
    return oc.validate_condition(row)


def conditions_flow(existing: list[dict[str, Any]] | None,
                    requirement_text: str | None, ask: Ask) -> list[dict[str, Any]]:
    """Keep, read, or edit the structured conditions behind an offer."""
    rows = [dict(c) for c in existing or []]
    while True:
        print("\n  Structured conditions:")
        print_conditions(rows)
        print("    k) keep   r) read from grade requirement   a) add   "
              "d) delete one   c) clear")
        cmd = ask("Choice", default="k").lower()
        if cmd == "k":
            return rows
        if cmd == "c":
            rows = []
        elif cmd == "r":
            if not (requirement_text or "").strip():
                print("    No grade requirement to read.")
                continue
            rows = oc.conditions_from_text(requirement_text)
            if len(rows) == 1 and rows[0]["kind"] == "other_text":
                print("    Could not be read in full — kept as one condition "
                      "checked by hand.")
        elif cmd == "a":
            try:
                rows.append(ask_condition(ask))
            except ValueError as e:
                print(f"    ✗ {e}")
        elif cmd == "d":
            raw = ask("Number to delete")
            if raw.isdigit() and 1 <= int(raw) <= len(rows):
                rows.pop(int(raw) - 1)
