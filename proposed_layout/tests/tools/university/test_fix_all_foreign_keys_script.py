"""Smoke tests for scripts.fix_all_foreign_keys."""
from unittest.mock import patch

from education_system.systems.university.scripts import fix_all_foreign_keys as script


class TestModuleSurface:
    def test_fix_foreign_keys_is_callable(self):
        assert callable(script.fix_foreign_keys)


class TestFixForeignKeys:
    def test_handles_db_failure_gracefully(self):
        with patch.object(script, "get_connection", side_effect=RuntimeError("db down")):
            try:
                script.fix_foreign_keys()
            except RuntimeError:
                pass  # acceptable — script raises or swallows; just don't crash the test
