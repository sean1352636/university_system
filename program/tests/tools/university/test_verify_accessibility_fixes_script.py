"""Smoke tests for scripts.verify_accessibility_fixes."""
from tools.university import verify_accessibility_fixes as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in (
            "verify_student_lookup",
            "verify_user_lookup",
            "verify_exam_lookup",
            "verify_exam_accommodations_schema",
            "verify_row_access_pattern",
            "verify_foreign_keys",
            "main",
        ):
            assert callable(getattr(script, name))
