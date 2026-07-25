"""Smoke tests for scripts.generate_test_fine_payments."""
from education_system.systems.university.scripts import generate_test_fine_payments as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in ("generate_test_payments", "show_summary", "main"):
            assert callable(getattr(script, name))
