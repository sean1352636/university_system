"""
Tests for university_system.modules.domain.academics.grade_misc.grade_db_init module.

This module tests the database initialization shim that imports from centralized schemas.
"""

from __future__ import annotations

import pytest

from university_system.modules.domain.academics.grading.grade_db_init import (
    init_basic_database,
)


class TestGradeDbInit:
    """Test grade database initialization"""

    def test_import_init_basic_database(self):
        """Test that init_basic_database can be imported"""
        assert init_basic_database is not None
        assert callable(init_basic_database)

    def test_init_basic_database_is_from_schemas(self):
        """Test that init_basic_database is actually from centralized schemas"""
        from university_system.infrastructure.database.schemas.core_schemas import (
            init_grade_system_db,
        )

        # Should be the same function
        assert init_basic_database is init_grade_system_db

    def test_module_exports(self):
        """Test that the module exports the expected items"""
        from university_system.modules.domain.academics.grading import (
            grade_db_init,
        )

        assert hasattr(grade_db_init, 'init_basic_database')
        assert grade_db_init.__all__ == ['init_basic_database']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
