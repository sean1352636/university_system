"""One terminal menu for a learner's whole route to university.

The CLI counterpart of :mod:`..views.window`, and it replaces the same
five entries the GUI lost: UCAS Applications, UCAS Workflow, Personal
Statements, References and University Offers.

It is a router, not a rewrite. Each area's ``run()`` is its own submenu
and is called unchanged, so every flow behaves exactly as it did — this
module adds one level above them, and two screens the terminal never
had:

**Overview**  the progression board. It had a GUI dashboard and no CLI
              at all, so "who is on the way out and what is stopping
              them" was unanswerable from a terminal or a headless
              results-day run.
**Learner**   one learner's application, choices, statement, reference
              and workflow position printed together — the same
              consolidation the window's Learner tab does, and the
              reason both exist.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    board as board_data,
    references as reference_data,
    statements as statement_data,
    ucas as ucas_data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression.university import (
    admissions_tests as admissions_tests_cli,
    deadlines as deadlines_cli,
    post_offer as post_offer_cli,
    student_finance as student_finance_cli,
    structured_references as structured_references_cli,
    offers as offers_cli,
    references as references_cli,
    statements as statements_cli,
    ucas as ucas_cli,
    workflow as workflow_cli,
)

logger = logging.getLogger(__name__)

#: The label this menu answers to, matched by :func:`dispatch`.
MENU_LABEL = "University & UCAS"


class _UserAbort(Exception):
    pass


def _pause() -> None:
    try:
        input("\n  Press Enter to continue…")
    except (EOFError, KeyboardInterrupt):
        print()


def _ask(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort from None
    return value or default


# ── Overview: the progression board ─────────────────────────────────

def _overview() -> None:
    """Print the board. The cohort question, in a terminal."""
    try:
        board = board_data.board()
    except Exception as exc:
        logger.exception("Could not build the progression board")
        print(f"\n  ✗ Could not build the board: {exc}")
        _pause()
        return

    print(f"\n── Progression board ──\n  {board.summary_line()}")
    if not board.rows:
        print("\n  Nobody is on the board. It draws from the Year 13 "
              "cohort, anyone holding a UCAS application, and any leaver "
              "whose handover never landed.")
        _pause()
        return

    print(f"\n  {'State':<16} {'Student':<12} {'Name':<24} "
          f"{'Destination':<26} Outstanding")
    print("  " + "─" * 100)
    for row in board.rows:
        outstanding = ", ".join(row.outstanding) or "—"
        print(f"  {row.state:<16} {row.student_id:<12} "
              f"{row.full_name[:23]:<24} "
              f"{(row.destination or '—')[:25]:<26} {outstanding[:34]}")
    # Warnings are louder than outstanding items and are what somebody
    # scanning this at 5pm on results day actually needs to see.
    for row in board.rows:
        for warning in row.warnings:
            print(f"\n  ! {row.student_id}: {warning}")
    _pause()


# ── Learner: one application, everything ────────────────────────────

def _predicted_grades(student_id: str):
    """``(subject, prediction_or_None)`` per A-level, or ``None``.

    The same read the window's strip does, and for the same reason: the
    UCAS workflow has a stage that turns on predicted grades while the
    screen that enters them lives in Assessment. Keyed on the subject
    string because that is what the stage matches on.
    """
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
            predicted_grades as _predicted,
        )
        student = _students.get_student(student_id)
        if student is None:
            return None
        subjects = [s for s in (student.subject_1, student.subject_2,
                                student.subject_3) if s]
        by_subject = {p.subject: p
                      for p in _predicted.predictions_for_student(student_id)}
        return [(subject, by_subject.get(subject)) for subject in subjects]
    except Exception:
        logger.debug("Could not read predicted grades for %s", student_id,
                     exc_info=True)
        return None

def _learner() -> None:
    """One learner's whole application on one screen."""
    rows = ucas_data.list_applications_with_detail()
    if not rows:
        print("\n  No UCAS applications yet.")
        _pause()
        return

    print("\n── Learner ──")
    for index, row in enumerate(rows, 1):
        application = row.application
        print(f"  {index}) {application.student_id:<12} "
              f"{row.student_name[:26]:<28} cycle {application.cycle_year}  "
              f"{application.status}")
    choice = _ask("Select (0 to go back)", default="0")
    if choice == "0":
        return
    if not choice.isdigit() or not (1 <= int(choice) <= len(rows)):
        print("  Invalid selection.")
        return
    _print_learner(rows[int(choice) - 1].application)
    _pause()


def _print_learner(application) -> None:
    print(f"\n═══ {application.student_id} — cycle {application.cycle_year} "
          f"═══")
    print(f"  Status        : {application.status}")
    print(f"  UCAS ID       : {application.ucas_id or '—'}")
    print(f"  Submitted     : {application.submitted_at or '—'}")

    print("\n  Choices")
    choices = ucas_data.list_choices(application.application_id)
    if not choices:
        print("    (none)")
    for choice in choices:
        code = f" ({choice.course_code})" if choice.course_code else ""
        print(f"    {choice.choice_order}. {choice.university} — "
              f"{choice.course_name}{code}")
        print(f"       {choice.decision_status}"
              + (f"  ·  {choice.offer_terms}" if choice.offer_terms else "")
              + (f"  ·  {choice.final_decision}"
                 if choice.final_decision else ""))

    print("\n  Predicted grades")
    predicted = _predicted_grades(application.student_id)
    if predicted is None:
        print("    Could not be read.")
    elif not predicted:
        print("    No A-level subjects on this student's record.")
    else:
        have = sum(1 for _subject, prediction in predicted if prediction)
        print(f"    {have}/{len(predicted)} subjects predicted"
              + ("" if have == len(predicted)
                 else "   (Assessment & Grades → Predicted Grades)"))
        for subject, prediction in predicted:
            grade = (f"{prediction.grade}"
                     + (f" ({prediction.confidence} confidence)"
                        if prediction.confidence else "")
                     if prediction else "— not predicted")
            print(f"      {subject:<26} {grade}")

    print("\n  Personal statement")
    drafts = statement_data.statements_for_student(application.student_id)
    if drafts:
        latest = drafts[0]
        print(f"    {latest.status}  ·  {latest.char_count}/"
              f"{statement_data.MAX_CHARS} chars  ·  {latest.line_count}/"
              f"{statement_data.MAX_LINES} lines"
              + (f"  ·  reviewed by {latest.reviewer}"
                 if latest.reviewer else ""))
        if (latest.char_count > statement_data.MAX_CHARS
                or latest.line_count > statement_data.MAX_LINES):
            print("    ! Over the UCAS limit — it cannot be submitted "
                  "until it is cut.")
    elif application.personal_statement:
        print("    On the UCAS application only — no draft here, so it "
              "has no review history or feedback.")
    else:
        print("    Not written yet.")

    print("\n  Academic reference")
    references = reference_data.references_for_student(application.student_id)
    submitted = next((r for r in references if r.status == "Submitted"),
                     references[0] if references else None)
    if submitted is None:
        print("    No reference requested yet.")
    else:
        print(f"    {submitted.status}"
              + (f"  ·  {submitted.referee}" if submitted.referee else "")
              + (f" ({submitted.referee_role})"
                 if submitted.referee_role else ""))

    print("\n  Workflow")
    try:
        pipeline = workflow_data.get_pipeline(
            application.student_id, application.cycle_year)
    except Exception as exc:
        logger.debug("Could not read the workflow pipeline", exc_info=True)
        print(f"    Pipeline unavailable: {exc}")
        return
    print(f"    {pipeline['complete']}/{pipeline['total']} stages complete "
          f"({pipeline['percent']}%)")
    marks = {"Complete": "✓", "N/A": "–", "In Progress": "…"}
    for stage in pipeline["stages"]:
        print(f"      {marks.get(stage['status'], '·')} {stage['label']}")


# ── Menu ────────────────────────────────────────────────────────────

#: Same order as the window's tabs, for the same reason: it is the
#: workflow, not the alphabet.
_MENU: tuple[tuple[str, object], ...] = (
    ("Overview — the progression board", _overview),
    ("Learner — one application, everything", _learner),
    ("Applications", ucas_cli.run),
    ("Personal statements", statements_cli.run),
    ("References", references_cli.run),
    ("Offers", offers_cli.run),
    ("Workflow", workflow_cli.run),
    ("Deadlines — UCAS dates, overdue and at risk", deadlines_cli.run),
    ("Admissions tests", admissions_tests_cli.run),
    ("Structured references (2026 entry on)", structured_references_cli.run),
    ("Extra, Clearing & Adjustment", post_offer_cli.run),
    ("Student finance (SFE)", student_finance_cli.run),
)


def run() -> None:
    while True:
        print(f"\n── {MENU_LABEL} ──")
        for index, (label, _handler) in enumerate(_MENU, 1):
            print(f"  {index}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _label, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("University & UCAS CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != MENU_LABEL:
        return False
    try:
        run()
    except Exception as e:
        logger.exception("University & UCAS CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True


__all__ = ["MENU_LABEL", "run", "dispatch"]
