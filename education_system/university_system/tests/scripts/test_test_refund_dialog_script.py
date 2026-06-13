"""Smoke tests for scripts.test_refund_dialog."""
from education_system.university_system.scripts import test_refund_dialog as script


class TestModuleSurface:
    def test_callable_exists(self):
        assert callable(script.test_query)
