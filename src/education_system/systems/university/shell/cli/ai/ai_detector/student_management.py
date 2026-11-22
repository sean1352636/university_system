"""Students in the CLI: readings over time for context, never a grade."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli


def _get_ai_detector():
    return _cli.detector()


def _student():
    module = _cli.pick_module()
    return _cli.pick_student(module) if module else None


def view_student_profile_cli():
    student = _student()
    if student:
        _cli.run(_get_ai_detector().view_student_profile, student, title=f"Student {student}")
        _cli.pause()


def compare_students_cli():
    first = _student()
    second = _student() if first else None
    if first and second:
        _cli.run(_get_ai_detector().compare_students, first, second,
                 title=f"{first} and {second}")
        _cli.pause()


def generate_student_report_card_cli():
    student = _student()
    if student:
        _cli.run(_get_ai_detector().generate_student_report_card, student,
                 title=f"Integrity summary — {student}")
        _cli.pause()


def flag_student_for_review_cli():
    student = _student()
    if not student:
        return
    reason = _cli.ask("Why should this student's work be looked at more closely?")
    if not reason:
        return
    severity = _cli.ask("Priority (low / medium / high)", "medium").lower()
    _cli.run(_get_ai_detector().flag_student_for_review, student, reason, severity=severity,
             title="Flagged")
    _cli.pause()


def view_student_progression_cli():
    student = _student()
    if student:
        _cli.run(_get_ai_detector().view_student_progression, student,
                 title=f"Readings over time — {student}")
        _cli.pause()


def bulk_student_analysis_cli():
    module = _cli.pick_module()
    if module:
        _cli.run(_get_ai_detector().bulk_student_analysis, course_code=module,
                 title=f"{module} — readings by student")
        _cli.pause()
