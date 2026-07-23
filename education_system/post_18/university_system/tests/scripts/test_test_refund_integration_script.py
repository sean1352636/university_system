"""Smoke tests for scripts.test_refund_integration."""
from education_system.post_18.university_system.scripts import test_refund_integration as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in (
            "test_library_refund",
            "test_dentist_refund",
            "test_gym_refund",
            "verify_refunds_in_finance_table",
            "main",
        ):
            assert callable(getattr(script, name))
