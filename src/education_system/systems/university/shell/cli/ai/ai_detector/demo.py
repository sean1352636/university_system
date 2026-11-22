"""What a reading looks like, on a fixed sample (nothing stored, no made-up
students), and the detector's component status."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli
from education_system.systems.university.shell.cli.ai.ai_detector.basic_operations import (
    EXAMPLE_TEXT,
)


def ultimate_demo():
    from education_system.systems.university.application.integrity import ai_indicators
    reading = ai_indicators.assess(EXAMPLE_TEXT, min_words=1)
    print("Example reading (fixed sample text; nothing stored)")
    _cli.print_reading({**reading, "result_id": "example", "submission_id": "—",
                        "student_id": "—", "course_code": "—"})


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ultimate_demo":
        ultimate_demo()
        return
    from education_system.systems.university.shared.ai.ai_detector.detector.main import (
        AIDetector,
    )
    detector = AIDetector()
    print("AI detector components that did not start:", detector.component_errors or "none")


if __name__ == "__main__":
    main()
