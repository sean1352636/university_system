"""Basic CLI operations: take a reading, history, statistics, and an
example reading of a fixed sample text (shown, not stored)."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli

EXAMPLE_TEXT = (
    "In today's fast-paced world, technology plays a pivotal role in education. Moreover, it "
    "is important to note that digital tools foster a sense of community. Furthermore, "
    "teachers must navigate the complexities of an ever-evolving landscape.")


def _get_ai_detector():
    return _cli.detector()


def analyze_text_interface_safe():
    """Take a reading of a text for a student on one of your modules."""
    print("\nTake a reading\n" + "=" * 30)
    module = _cli.pick_module()
    if not module:
        return
    student = _cli.pick_student(module)
    if not student:
        return
    assignment = _cli.pick_assignment(module)
    title = _cli.ask("Title (optional)") or None
    text, file_type = _cli.read_text()
    if not text:
        print("  No text given.")
        return
    try:
        result = _get_ai_detector().analyze_text(text=text, title=title, student_id=student,
                                                 course_code=module, assignment_id=assignment,
                                                 file_type=file_type)
    except (PermissionError, ValueError) as exc:
        print(f"  No reading taken: {exc}")
        return
    display_analysis_results_safe(result, text)


def display_analysis_results_safe(result, text=None):
    _cli.print_reading(result)
    _cli.offer_sentences(result, text)
    _cli.pause()


def view_submission_history_safe():
    """Readings on your modules, newest first; open one for detail."""
    try:
        data = _get_ai_detector().get_submission_history(limit=50)
    except (PermissionError, ValueError) as exc:
        print(f"  {exc}")
        return
    rows = data.get("submissions", [])
    if not rows:
        print("  No readings yet.")
        _cli.pause()
        return
    print(f"\n{'Sub':>5} {'Reading':>7}  {'Student':<10} {'Module':<10} {'Level':<22} Title")
    for s in rows:
        print(f"{s.get('id'):>5} {s.get('result_id') or '':>7}  {str(s.get('student_id')):<10} "
              f"{str(s.get('course_code') or ''):<10} {str(s.get('level') or '—'):<22} "
              f"{s.get('title')}")
    value = _cli.ask("\nSubmission id to open (Enter to go back)")
    if value.isdigit():
        try:
            display_detailed_submission(_get_ai_detector().get_submission_details(int(value)))
        except (PermissionError, ValueError) as exc:
            print(f"  {exc}")


def display_detailed_submission(submission):
    reading = submission.get("detailed_results") or {}
    result = {**reading, "needs_review": submission.get("needs_review"),
              "result_id": submission.get("result_id"), "submission_id": submission.get("id"),
              "student_id": submission.get("student_id"),
              "course_code": submission.get("course_code"),
              "informational": (reading.get("detector") or {}).get("informational")}
    _cli.print_reading(result)
    if not reading.get("indicators"):
        print("  Taken before indicators were recorded; its score is not reliable.")
    _cli.offer_sentences({**result, "indicators": reading.get("indicators"),
                          "passages": reading.get("passages")},
                         submission.get("submission_text"))
    _cli.pause()


def view_ai_detector_statistics_safe():
    _cli.run(_get_ai_detector().get_enhanced_statistics, title="Readings on your modules")
    _cli.pause()


def run_ai_detector_demo_safe():
    """What a reading looks like, on a fixed sample (not stored)."""
    from education_system.systems.university.application.integrity import ai_indicators
    reading = ai_indicators.assess(EXAMPLE_TEXT, min_words=1)
    print("\nExample (fixed sample text, nothing stored):")
    _cli.print_reading({**reading, "result_id": "example", "submission_id": "—",
                        "student_id": "—", "course_code": "—"})
    _cli.pause()
