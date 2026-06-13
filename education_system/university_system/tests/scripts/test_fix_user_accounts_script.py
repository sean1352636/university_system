"""Smoke tests for scripts.fix_user_accounts."""
from education_system.university_system.scripts import fix_user_accounts as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in (
            "analyze_database",
            "fix_system_account",
            "clean_duplicate_mappings",
            "verify_integrity",
            "main",
        ):
            assert callable(getattr(script, name))
