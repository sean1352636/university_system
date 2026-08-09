"""Smoke tests for scripts.diagnose_refund_dialog."""
from tools.university import diagnose_refund_dialog as script


class TestModuleSurface:
    def test_callable_exists(self):
        assert callable(script.test_query)
