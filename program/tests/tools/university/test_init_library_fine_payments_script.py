"""Smoke tests for scripts.init_library_fine_payments."""
from tools.university import init_library_fine_payments as script


class TestModuleSurface:
    def test_callables_exist(self):
        for name in ("init_library_fine_payments_table", "migrate_existing_payments",
                     "verify_setup", "main"):
            assert callable(getattr(script, name))
